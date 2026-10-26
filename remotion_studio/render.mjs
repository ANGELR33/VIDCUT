/**
 * Render de una composición Remotion a MOV ProRes 4444 con canal alpha.
 *
 * Uso:  node render.mjs <props.json> <salida.mov> [composición=KaiCaptions] [--still=<seg>]
 *
 * - El bundle de Webpack se genera UNA vez en ./build y se reutiliza mientras
 *   los fuentes (src/) no cambien (el empaquetado cuesta ~15 s; el render por
 *   escena solo paga el arranque del navegador).
 * - Con --still=<segundos> exporta un PNG de ese instante (para depurar diseño).
 */
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const buildDir = path.join(here, "build");
const srcDir = path.join(here, "src");

const args = process.argv.slice(2);
const flags = Object.fromEntries(
  args
    .filter((a) => a.startsWith("--"))
    .map((a) => {
      const [k, v] = a.replace(/^--/, "").split("=");
      return [k, v ?? true];
    })
);
const positional = args.filter((a) => !a.startsWith("--"));
const [propsPath, outPath, compositionId = "KaiCaptions"] = positional;

if (!propsPath || !outPath) {
  console.error("Uso: node render.mjs <props.json> <salida> [composición] [--still=seg]");
  process.exit(2);
}

const newestMtime = (dir) => {
  let newest = 0;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    newest = Math.max(
      newest,
      entry.isDirectory() ? newestMtime(p) : fs.statSync(p).mtimeMs
    );
  }
  return newest;
};

const ensureBundle = async () => {
  const marker = path.join(buildDir, "index.html");
  const fresh =
    fs.existsSync(marker) && fs.statSync(marker).mtimeMs >= newestMtime(srcDir);
  if (fresh) return buildDir;
  // Se empaqueta en una carpeta temporal y se promueve de forma atómica para
  // que un render concurrente nunca lea un bundle a medio escribir.
  const tmpDir = path.join(here, `build_tmp_${process.pid}`);
  await bundle({
    entryPoint: path.join(srcDir, "index.ts"),
    outDir: tmpDir,
  });
  fs.rmSync(buildDir, { recursive: true, force: true });
  fs.renameSync(tmpDir, buildDir);
  return buildDir;
};

const main = async () => {
  const inputProps = JSON.parse(fs.readFileSync(propsPath, "utf-8"));
  const serveUrl = await ensureBundle();
  const composition = await selectComposition({
    serveUrl,
    id: compositionId,
    inputProps,
    logLevel: "error",
  });

  if (flags.still) {
    const frame = Math.min(
      composition.durationInFrames - 1,
      Math.round(Number(flags.still) * composition.fps)
    );
    await renderStill({
      composition,
      serveUrl,
      output: outPath,
      frame,
      inputProps,
      logLevel: "error",
    });
    console.log(`STILL_OK ${outPath}`);
    return;
  }

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  await renderMedia({
    composition,
    serveUrl,
    codec: "prores",
    proResProfile: "4444",
    pixelFormat: "yuva444p10le",
    imageFormat: "png",
    outputLocation: outPath,
    inputProps,
    overwrite: true,
    concurrency: Math.max(2, Math.min(6, Math.floor(os.cpus().length / 2))),
    logLevel: "error",
    timeoutInMilliseconds: 120000,
  });
  console.log(`RENDER_OK ${outPath}`);
};

main().catch((err) => {
  console.error("RENDER_FAIL", err?.message || err);
  process.exit(1);
});
