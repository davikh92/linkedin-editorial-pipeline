/**
 * render_image.js — renderiza o template de overlay e salva o PNG final do post.
 *
 * Camada 3 da tecnica de 3 camadas:
 *   1. fundo fotografico (gerado pelo Gemini, chega aqui como data-URI no payload)
 *   2. texto em HTML/CSS (templates/post-overlay.html)
 *   3. screenshot 1200x1200 via Puppeteer  <- este arquivo
 *
 * Uso:  node render_image.js <payload.json> <saida.png>
 *
 * O payload e o objeto injetado como window.POST_DATA:
 *   {template, kicker, headline, subtext, numero, passos[], bgDataUri}
 *
 * Puppeteer vem de instagram/node_modules (nao duplicamos a dependencia).
 */
const fs = require('fs');
const path = require('path');

const PUPPETEER_DIR = path.join(__dirname, '..', 'instagram');
const puppeteer = require(require.resolve('puppeteer', { paths: [PUPPETEER_DIR] }));

const TEMPLATE = path.join(__dirname, 'templates', 'post-overlay.html');
const SIZE = 1200;

async function main() {
  const [payloadPath, outPath] = process.argv.slice(2);
  if (!payloadPath || !outPath) {
    console.error('Uso: node render_image.js <payload.json> <saida.png>');
    process.exit(2);
  }

  const data = JSON.parse(fs.readFileSync(payloadPath, 'utf8'));

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--font-render-hinting=none'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: SIZE, height: SIZE, deviceScaleFactor: 1 });

    // POST_DATA precisa existir ANTES do script inline do template rodar
    await page.evaluateOnNewDocument((d) => { window.POST_DATA = d; }, data);

    // networkidle0 garante que as fontes do Google terminaram de carregar
    await page.goto('file://' + TEMPLATE.replace(/\\/g, '/'), {
      waitUntil: 'networkidle0',
      timeout: 60000,
    });

    await page.waitForFunction('window.__READY__ === true', { timeout: 15000 });
    // garante que o layout ja reflete a fonte final, nao a fallback
    await page.evaluate(() => document.fonts.ready);

    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    await page.screenshot({ path: outPath, type: 'png' });
    console.log('OK ' + outPath);
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error('ERRO: ' + (err && err.message ? err.message : String(err)));
  process.exit(1);
});
