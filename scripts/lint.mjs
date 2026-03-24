import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const dataPath = path.join(root, "data", "methodensammlung.json");
const appPaths = [
  path.join(root, "index.html"),
  path.join(root, "styles", "main.css"),
  path.join(root, "src", "main.js"),
  path.join(root, "src", "data-model.js"),
];

for (const target of [...appPaths, dataPath]) {
  if (!fs.existsSync(target)) {
    console.error(`Missing required app artifact: ${path.relative(root, target)}`);
    process.exit(1);
  }
}

const bundle = fs.readFileSync(dataPath, "utf8");
const forbiddenMockupTitles = [
  "The Human Mirror",
  "The Socratic Mirror",
  "Human Mirror Protocol",
  "The Warm Arrival",
  "The Collective Harvest",
  "The Silent Brain-Write",
];

for (const title of forbiddenMockupTitles) {
  if (bundle.includes(title)) {
    console.error(`Generated data still contains forbidden mockup title: ${title}`);
    process.exit(1);
  }
}

console.log("Lint passed.");
