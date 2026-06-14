// Run with: npx tsx src/lib/generate-icons.ts
// Generates placeholder PNG icons for the extension

import { writeFileSync } from "fs";

function createPNG(size: number): Buffer {
  // Minimal valid PNG with a blue square
  const width = size;
  const height = size;

  // PNG signature
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  // IHDR chunk
  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(width, 0);
  ihdrData.writeUInt32BE(height, 4);
  ihdrData[8] = 8; // bit depth
  ihdrData[9] = 2; // color type (RGB)
  ihdrData[10] = 0; // compression
  ihdrData[11] = 0; // filter
  ihdrData[12] = 0; // interlace

  const ihdr = createChunk("IHDR", ihdrData);

  // IDAT chunk - uncompressed image data
  const rawData: number[] = [];
  for (let y = 0; y < height; y++) {
    rawData.push(0); // filter byte
    for (let x = 0; x < width; x++) {
      // Blue gradient icon
      const r = 37;
      const g = 99;
      const b = 235;
      rawData.push(r, g, b);
    }
  }

  // Deflate with no compression (store)
  const raw = Buffer.from(rawData);
  const blocks: Buffer[] = [];

  const BLOCK_SIZE = 65535;
  for (let i = 0; i < raw.length; i += BLOCK_SIZE) {
    const isLast = i + BLOCK_SIZE >= raw.length;
    const block = raw.subarray(i, Math.min(i + BLOCK_SIZE, raw.length));
    const header = Buffer.alloc(5);
    header[0] = isLast ? 1 : 0;
    header.writeUInt16LE(block.length, 1);
    header.writeUInt16LE(~block.length & 0xffff, 3);
    blocks.push(header, block);
  }

  // zlib header (no compression) + adler32
  const zlibHeader = Buffer.from([0x78, 0x01]);
  const adler = adler32(raw);
  const adlerBuf = Buffer.alloc(4);
  adlerBuf.writeUInt32BE(adler, 0);

  const compressed = Buffer.concat([zlibHeader, ...blocks, adlerBuf]);
  const idat = createChunk("IDAT", compressed);

  // IEND chunk
  const iend = createChunk("IEND", Buffer.alloc(0));

  return Buffer.concat([signature, ihdr, idat, iend]);
}

function createChunk(type: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length, 0);

  const typeBuffer = Buffer.from(type, "ascii");
  const crcData = Buffer.concat([typeBuffer, data]);
  const crc = crc32(crcData);
  const crcBuffer = Buffer.alloc(4);
  crcBuffer.writeUInt32BE(crc, 0);

  return Buffer.concat([length, typeBuffer, data, crcBuffer]);
}

function crc32(buf: Buffer): number {
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc ^= buf[i];
    for (let j = 0; j < 8; j++) {
      crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function adler32(buf: Buffer): number {
  let a = 1,
    b = 0;
  for (let i = 0; i < buf.length; i++) {
    a = (a + buf[i]) % 65521;
    b = (b + a) % 65521;
  }
  return ((b << 16) | a) >>> 0;
}

for (const size of [16, 48, 128]) {
  const png = createPNG(size);
  writeFileSync(`public/icons/icon${size}.png`, png);
  console.log(`Created icon${size}.png`);
}
