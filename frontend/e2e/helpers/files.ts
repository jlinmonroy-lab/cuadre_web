// Archivos sintéticos para subir en las pruebas (RES-07, T2-12): se generan aquí, no hay ninguno en el repositorio.
//
// Cada uno lleva dentro un marcador `[[fixture:<nombre>[>otro][;delay=<ms>]]]` que elige qué «lee» el servidor de agentes de E2E
// (`backend/tests/agents/e2e_server.py`); las pruebas pasan `fixture:<nombre>…` y aquí se cierra entre corchetes dobles. El cierre es
// necesario: en un PNG los bytes del CRC van pegados al texto y, sin él, una letra como primer byte se pegaría al nombre.
// Son archivos válidos para la API (firma de PDF y de PNG) y el PNG se pinta en un navegador.
import { randomUUID } from "node:crypto";
import { deflateSync } from "node:zlib";

export type UploadFile = { name: string; mimeType: string; buffer: Buffer };

/** Nombre único (las pruebas buscan su documento por el nombre, y una misma cuenta acumula los de varias pruebas). */
export function uniqueName(tag: string, extension: "pdf" | "png"): string {
  return `${tag}-${randomUUID().slice(0, 8)}.${extension}`;
}

const closed = (marker: string): string => `[[${marker}]]`;

export function pdfFile(name: string, marker: string): UploadFile {
  const text = `%PDF-1.4\n%${closed(marker)}\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n`;
  return { name, mimeType: "application/pdf", buffer: Buffer.from(text, "latin1") };
}

function crc32(buffer: Buffer): number {
  let crc = ~0;
  for (const byte of buffer) {
    crc ^= byte;
    for (let k = 0; k < 8; k++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return ~crc >>> 0;
}

function chunk(type: string, data: Buffer): Buffer {
  const body = Buffer.concat([Buffer.from(type, "latin1"), data]);
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

/** PNG de rayas (200 × 120), con el marcador en un trozo `tEXt`. */
export function pngFile(name: string, marker: string): UploadFile {
  const width = 200;
  const height = 120;
  const rows: Buffer[] = [];
  for (let y = 0; y < height; y++) {
    const row = Buffer.alloc(1 + width * 3);
    const stripe = Math.floor(y / 20) % 2 === 0;
    for (let x = 0; x < width; x++) {
      row[1 + x * 3] = stripe ? 90 : 235;
      row[2 + x * 3] = stripe ? 120 : 240;
      row[3 + x * 3] = stripe ? 100 : 236;
    }
    rows.push(row);
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 2, 0, 0, 0], 8); // 8 bits, RGB, sin entrelazado
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("tEXt", Buffer.from(`Comment\0${closed(marker)}`, "latin1")),
    chunk("IDAT", deflateSync(Buffer.concat(rows))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
  return { name, mimeType: "image/png", buffer: png };
}
