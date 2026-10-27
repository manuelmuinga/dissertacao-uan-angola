const { chromium } = require('playwright');
const B = 'http://127.0.0.1:8000';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1366, height: 768 }, recordVideo: { dir: 'video', size: { width: 1366, height: 768 } } });
  const p = await ctx.newPage();
  const w = (s) => p.waitForTimeout(s * 1000);
  const leg = async (t) => { await p.evaluate((t) => {
    let d = document.getElementById('legenda-video');
    if (!d) { d = document.createElement('div'); d.id = 'legenda-video';
      d.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:1000px;background:rgba(15,23,42,.88);color:#fff;font:600 19px/1.4 system-ui,sans-serif;padding:12px 20px;border-radius:10px;z-index:99999;text-align:center;pointer-events:none';
      document.body.appendChild(d); }
    d.textContent = t; }, t); };
  const ir = async (u, t) => { await p.goto(B + u); await p.waitForLoadState('networkidle'); const s = p.locator('button:has-text("Saltar")'); if (await s.isVisible().catch(() => false)) await s.click(); await w(0.6); if (t) await leg(t); };
  const rolar = async (px, passos = 6, s = 0.5) => { for (let i = 0; i < passos; i++) { await p.mouse.wheel(0, px / passos); await w(s); } };

  // Entrada
  await p.goto(B + '/'); await leg('Sistema UAN · modo de demonstração · dados fictícios: nenhuma pessoa real é descrita');
  await w(3); await p.fill('#u', 'demo.supervisor'); await w(0.5); await p.fill('#s', 'demonstracao'); await w(0.5);
  await p.click('button[type=submit]'); await p.waitForLoadState('networkidle');
  { const s = p.locator('button:has-text("Saltar")'); if (await s.isVisible().catch(() => false)) await s.click(); }
  // 1. Panorama (0:25)
  await leg('1 · Panorama: o que foi recolhido e o que o modelo sinalizou, por categoria e por período');
  await w(8); await rolar(500, 5, 1); await w(5); await rolar(-500, 2, 0.5); await w(3);
  // 2. Fila (1:00)
  await ir('/fila', '2 · Fila de revisão: ordenada pela probabilidade de não ser Normal');
  await w(8);
  await leg('O analista lê a publicação, vê as probabilidades e o lugar realçado, e decide com uma tecla');
  await w(6);
  await p.keyboard.press('4'); await leg('Decisão com a tecla 4 (Mobilização Hostil)…'); await w(5);
  await p.keyboard.press('u'); await leg('…e U desfaz. A decisão é sempre do analista'); await w(6);
  await leg('Em parte da fila a sugestão do modelo fica escondida: revisão cega, contra o viés de automação'); await rolar(700, 5, 1); await w(5);
  await ir('/amostra', 'Amostra de controlo: itens que o modelo considerou Normais, para medir o que ele deixa escapar');
  await w(14);
  // 3. Alertas e mapa (1:00)
  await ir('/', '3 · Alertas em tempo real; nunca são enviados a terceiros');
  await p.click('button.sino').catch(() => {}); await w(8); await p.keyboard.press('Escape'); await w(1);
  await ir('/mapa', 'Mapa: agregados por província, nunca pessoas. A província é o lugar mencionado, não quem escreve');
  await w(5);
  const lua = p.locator('svg text', { hasText: 'LUA' }).first(); if (await lua.count()) { const bb = await lua.boundingBox(); if (bb) { await p.mouse.move(bb.x + bb.width / 2, bb.y + bb.height + 12, { steps: 15 }); } await w(6); }
  await leg('Reproduzir: a evolução semana a semana');
  await p.click('button:has-text("Reproduzir")').catch(() => {}); await w(22);
  await rolar(600, 4, 1); await w(5);
  // 4. Sobre o modelo (0:30)
  await ir('/modelo', '4 · Sobre o modelo: o desempenho em conteúdo angolano (0,53) e onde o modelo falha');
  await w(10); await rolar(700, 5, 1.2); await w(10);
  // 5. Fontes e recuperação (0:40)
  await ir('/lotes', '5 · Lotes: cada recolha ou importação fica registada com plataforma, via, data e volume');
  await w(12); await ir('/fontes', 'A recolha usa a API oficial ou páginas públicas sem conta (na demonstração está desligada)');
  await w(7);
  await p.click('button:has-text("Sair")').catch(() => {}); await p.waitForLoadState('networkidle');
  await ir('/recuperar', 'Recuperação do acesso sem correio electrónico: código de uso único ou pedido ao supervisor');
  await w(14);
  await leg('Fim da demonstração'); await w(3);
  await ctx.close(); await b.close();
})();
