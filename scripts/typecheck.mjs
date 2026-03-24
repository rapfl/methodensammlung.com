import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "data", "methodensammlung.json");

if (!fs.existsSync(dataPath)) {
  console.error("Missing generated data bundle. Run `npm run build:data` first.");
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
const sheets = data.sheets ?? {};

const requiredSheets = [
  "methods",
  "methodTags",
  "methodVariants",
  "finderIntents",
  "collections",
  "collectionItems",
  "vectors",
  "methodVectorMap",
  "composerBlocksReference",
  "uiFieldMapping",
  "mockupConstraints",
  "openQuestions",
];

for (const sheet of requiredSheets) {
  if (!Array.isArray(sheets[sheet])) {
    console.error(`Sheet ${sheet} is missing or not an array.`);
    process.exit(1);
  }
}

const methods = sheets.methods;
const variants = sheets.methodVariants;
const collections = sheets.collections;
const vectors = sheets.vectors;
const blockRefs = sheets.composerBlocksReference;
const methodIds = new Set(methods.map((item) => item.method_id));
const variantIds = new Set(variants.map((item) => item.variant_id));
const collectionIds = new Set(collections.map((item) => item.collection_id));
const vectorIds = new Set(vectors.map((item) => item.vector_id));

if (methods.length !== 82) {
  console.error(`Expected 82 methods, found ${methods.length}.`);
  process.exit(1);
}

for (const method of methods) {
  if (!method.method_id || !method.name_de) {
    console.error("Every method requires a stable id and canonical title.");
    process.exit(1);
  }
}

for (const variant of variants) {
  if (!methodIds.has(variant.method_id)) {
    console.error(`Variant ${variant.variant_id} points to missing method ${variant.method_id}.`);
    process.exit(1);
  }
}

for (const item of sheets.collectionItems) {
  if (!collectionIds.has(item.collection_id)) {
    console.error(`Collection item points to missing collection ${item.collection_id}.`);
    process.exit(1);
  }
  const sourceId = item.method_id_or_variant_id;
  if (!(methodIds.has(sourceId) || variantIds.has(sourceId))) {
    console.error(`Collection item points to missing source ${sourceId}.`);
    process.exit(1);
  }
}

for (const item of sheets.methodVectorMap) {
  if (!methodIds.has(item.method_id)) {
    console.error(`Vector map points to missing method ${item.method_id}.`);
    process.exit(1);
  }
  if (!vectorIds.has(item.vector_id)) {
    console.error(`Vector map points to missing vector ${item.vector_id}.`);
    process.exit(1);
  }
}

for (const block of blockRefs) {
  const exists = block.source_type === "variant" ? variantIds.has(block.source_id) : methodIds.has(block.source_id);
  if (!exists) {
    console.error(`Composer block ${block.block_ref_id} points to missing ${block.source_type} ${block.source_id}.`);
    process.exit(1);
  }
}

console.log("Typecheck passed.");
