// Apresentação da defesa da dissertação (20 minutos), gerada com pptxgenjs.
const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const sharp = require('sharp');
const Fa = require('react-icons/fa');
const { applyTheme } = require('/root/.claude/skills/synced/c839fb96-0e54-447b-bc7f-f0f3174d226d_45b15fb7-6316-4503-930d-730f8784abae/pptx/scripts/apply_theme.js');

const THEME = {
  name: 'Defesa UAN',
  headFontFace: 'Arial',
  bodyFontFace: 'Arial',
  colors: {
    dk1: '1B2733', lt1: 'FFFFFF', dk2: '102A43', lt2: 'EEF2F6',
    accent1: '102A43', accent2: 'C8102E', accent3: 'E8B931', accent4: '2E6F9E', accent5: '5B6B7F', accent6: '178A5F',
    hlink: '2E6F9E', folHlink: '5B6B7F',
  },
};
const HEX = THEME.colors;
const NAVY = '102A43', RED = 'C8102E', GOLD = 'E8B931', BLUE = '2E6F9E', GREY = '5B6B7F', LIGHT = 'EEF2F6', LINE = 'CBD2D9', GREEN = '178A5F';

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13,33 × 7,5 pol.
pres.author = 'Manuel Gonga Muinga';
pres.title = 'Monitoramento inteligente de ameaças em redes sociais em Angola';
pres.subject = 'Defesa de dissertação de mestrado, UAN, 2026';
pres.theme = { headFontFace: 'Arial', bodyFontFace: 'Arial' };
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, MX = 0.6;

// ---------------------------------------------------------------- ícones
async function icone(nome, cor = 'FFFFFF', tam = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Fa[nome], { color: '#' + cor, size: tam }));
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return 'image/png;base64,' + png.toString('base64');
}

// ---------------------------------------------------------------- layouts
pres.defineSlideMaster({
  title: 'CONTEUDO',
  background: { color: 'FFFFFF' },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: MX, y: 0.82, w: W - 2 * MX, h: 0.78, fontFace: 'Arial', fontSize: 28, bold: true, color: NAVY, valign: 'middle', margin: 0 }, text: 'Título' } },
    { text: { text: 'Manuel Gonga Muinga · Defesa de dissertação · UAN, 2026', options: { x: MX, y: H - 0.42, w: 7, h: 0.28, fontFace: 'Arial', fontSize: 10, color: GREY, margin: 0 } } },
  ],
  slideNumber: { x: W - MX - 0.6, y: H - 0.42, w: 0.6, h: 0.28, fontFace: 'Arial', fontSize: 10, color: GREY, align: 'right' },
});
pres.defineSlideMaster({ title: 'ESCURO', background: { color: NAVY }, objects: [] });

// ---------------------------------------------------------------- agenda no topo
const SECCOES = ['Introdução', 'Revisão da literatura', 'Metodologia', 'Resultados', 'Sistema', 'Conclusões'];
function agendaTopo(slide, atual) {
  const gap = 0.12, larg = (W - 2 * MX - gap * (SECCOES.length - 1)) / SECCOES.length;
  SECCOES.forEach((s, i) => {
    const x = MX + i * (larg + gap);
    const estado = i < atual ? 'feito' : i === atual ? 'actual' : 'futuro';
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: 0.24, w: larg, h: 0.36, rectRadius: 0.18,
      fill: { color: estado === 'actual' ? NAVY : estado === 'feito' ? LIGHT : 'FFFFFF' },
      line: { color: estado === 'actual' ? NAVY : LINE, width: 0.75 },
      objectName: `agenda-${i + 1}`,
    });
    slide.addText(`${i + 1}. ${s}`, {
      x, y: 0.24, w: larg, h: 0.36, align: 'center', valign: 'middle', margin: 0, isTextBox: true,
      fontSize: 11, bold: estado === 'actual', color: estado === 'actual' ? 'FFFFFF' : estado === 'feito' ? GREY : '8A96A3',
      objectName: `agenda-texto-${i + 1}`,
    });
  });
}

function legenda(slide, texto, x, y, w, fonte) {
  slide.addText([{ text: texto, options: { bold: true, breakLine: !!fonte } }, ...(fonte ? [{ text: fonte, options: { italic: true, color: GREY } }] : [])],
    { x, y, w, h: fonte ? 0.5 : 0.3, fontSize: 10, color: C.text1, align: 'center', margin: 0, isTextBox: true, objectName: 'legenda' });
}

function cartao(slide, x, y, w, h, nome) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08, fill: { color: LIGHT }, line: { color: LIGHT }, objectName: nome,
  });
}

let nSlide = 0;
const tempos = [];
function novo(seccao, sec, notas, tempo) {
  const s = pres.addSlide({ masterName: 'CONTEUDO', sectionTitle: seccao });
  if (sec !== null) agendaTopo(s, sec);
  nSlide += 1;
  tempos.push(tempo);
  const acum = tempos.reduce((a, b) => a + b, 0);
  const mmss = (t) => `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
  s.addNotes(`Tempo deste diapositivo: ${mmss(tempo)} (relógio no fim: ${mmss(acum)} de 20:00).\n\n${notas}`);
  return s;
}

(async () => {
  const ic = {};
  for (const [k, n, cor] of [
    ['globo', 'FaGlobeAfrica', 'FFFFFF'], ['lupa', 'FaSearch', 'FFFFFF'], ['livro', 'FaBook', 'FFFFFF'],
    ['escudo', 'FaShieldAlt', 'FFFFFF'], ['utilizador', 'FaUserCheck', 'FFFFFF'], ['cadeado', 'FaLock', 'FFFFFF'],
    ['bd', 'FaDatabase', 'FFFFFF'], ['wifi', 'FaPlug', 'FFFFFF'], ['teste', 'FaCheckDouble', 'FFFFFF'],
    ['olho', 'FaUserSecret', 'FFFFFF'], ['grafico', 'FaChartLine', 'FFFFFF'], ['rede', 'FaProjectDiagram', 'FFFFFF'],
    ['relogio', 'FaClock', 'FFFFFF'], ['monitor', 'FaDesktop', 'FFFFFF'], ['seta', 'FaArrowRight', 'FFFFFF'],
  ]) ic[k] = await icone(n, cor);
  const circulo = (slide, x, y, d, img, cor = NAVY) => {
    slide.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: cor }, line: { color: cor }, objectName: 'icone-circulo' });
    slide.addImage({ data: img, x: x + d * 0.25, y: y + d * 0.25, w: d * 0.5, h: d * 0.5, objectName: 'icone' });
  };

  // ============================================================ 1. Capa
  pres.addSection({ title: 'Abertura' });
  {
    const s = pres.addSlide({ masterName: 'ESCURO', sectionTitle: 'Abertura' });
    nSlide += 1; tempos.push(30);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 0.45, w: 2.3, h: 1.05, rectRadius: 0.1, fill: { color: 'FFFFFF' }, line: { color: 'FFFFFF' }, objectName: 'fundo-logos' });
    s.addImage({ path: 'logo_uan.png', x: MX + 0.2, y: 0.55, w: 0.83, h: 0.85, objectName: 'logo-UAN' });
    s.addImage({ path: 'logo_fe.png', x: MX + 1.27, y: 0.55, w: 0.81, h: 0.85, objectName: 'logo-FE' });
    s.addText([{ text: 'UNIVERSIDADE AGOSTINHO NETO', options: { bold: true, breakLine: true } }, { text: 'FACULDADE DE ENGENHARIA', options: {} }],
      { x: 3.15, y: 0.55, w: 6, h: 0.85, fontSize: 14, color: 'FFFFFF', valign: 'middle', margin: 0, isTextBox: true });
    s.addText('Monitoramento inteligente de ameaças em redes sociais em Angola para o apoio à defesa e segurança nacional',
      { x: MX, y: 1.95, w: 11.6, h: 1.7, fontSize: 32, bold: true, color: 'FFFFFF', valign: 'top', margin: 0, isTextBox: true, objectName: 'titulo' });
    s.addText('Dissertação para obtenção do grau de Mestre em Engenharia e Ciência de Dados',
      { x: MX, y: 3.75, w: 11.6, h: 0.45, fontSize: 18, color: GOLD, margin: 0, isTextBox: true });
    s.addText([
      { text: 'Mestrando: ', options: { color: 'B8C4D1' } }, { text: 'Manuel Gonga Muinga, Engenheiro Electrotécnico', options: { bold: true, breakLine: true } },
      { text: 'Orientador: ', options: { color: 'B8C4D1' } }, { text: 'Professor Doutor Joaquim Fortes', options: { breakLine: true } },
      { text: 'Co-orientador: ', options: { color: 'B8C4D1' } }, { text: 'Professor Doutor Judice Cumbunga', options: {} },
    ], { x: MX, y: 4.55, w: 8.5, h: 1.3, fontSize: 16, color: 'FFFFFF', margin: 0, paraSpaceAfter: 6, isTextBox: true });
    s.addText('Luanda, 2026', { x: MX, y: 6.55, w: 4, h: 0.4, fontSize: 16, color: 'FFFFFF', margin: 0, isTextBox: true });
    s.addNotes('Tempo deste diapositivo: 0:30 (relógio no fim: 0:30 de 20:00).\n\nCumprimentar o Presidente do Júri, os membros do júri, os orientadores e o público. Apresentar o título e o enquadramento: dissertação de mestrado em Engenharia e Ciência de Dados. Anunciar que a exposição dura 20 minutos e inclui uma demonstração do sistema.');
  }

  // ============================================================ 2. Agenda
  {
    const s = novo('Abertura', null, 'Apresentar a estrutura: seis partes. Indicar que a parte maior é a do sistema, com demonstração ao vivo, e que no topo de cada diapositivo se vê em que parte estamos.', 30);
    s.addText('Agenda', { placeholder: 'title' });
    const itens = [
      ['1', 'Introdução', 'Contexto, pergunta, hipóteses e objectivos', '2:45'],
      ['2', 'Revisão da literatura', 'O que se sabe e a lacuna para Angola', '1:15'],
      ['3', 'Metodologia', 'Desenho, corpus angolano, corpus híbrido e modelos', '2:45'],
      ['4', 'Resultados', 'Modelos, lacuna de domínio, fila, tempo e limitações', '4:30'],
      ['5', 'Sistema', 'Arquitectura e demonstração ao vivo', '5:00'],
      ['6', 'Conclusões', 'Hipóteses, conclusões e recomendações', '2:45'],
    ];
    itens.forEach(([n, t, d, m], i) => {
      const col = i % 2, lin = Math.floor(i / 2);
      const x = MX + col * 6.15, y = 1.9 + lin * 1.55;
      cartao(s, x, y, 5.95, 1.3, `agenda-cartao-${n}`);
      s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.3, w: 0.7, h: 0.7, fill: { color: n === '5' ? RED : NAVY }, line: { color: n === '5' ? RED : NAVY } });
      s.addText(n, { x: x + 0.25, y: y + 0.3, w: 0.7, h: 0.7, fontSize: 20, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0, isTextBox: true });
      s.addText([{ text: t, options: { bold: true, fontSize: 18, color: NAVY, breakLine: true } }, { text: d, options: { fontSize: 14, color: C.text1 } }],
        { x: x + 1.15, y: y + 0.17, w: 3.75, h: 0.96, valign: 'middle', margin: 0, isTextBox: true });
      s.addText(m, { x: x + 4.85, y: y + 0.4, w: 0.9, h: 0.5, fontSize: 16, bold: true, color: n === '5' ? RED : BLUE, align: 'right', valign: 'middle', margin: 0, isTextBox: true });
    });
    s.addText('Exposição: 20 minutos. A abertura (capa e agenda) ocupa 1:00 e as seis partes somam 19:00.',
      { x: MX, y: 6.6, w: W - 2 * MX, h: 0.35, fontSize: 11, color: GREY, margin: 0, isTextBox: true });
  }

  // ============================================================ 3. Contexto
  pres.addSection({ title: 'Introdução' });
  {
    const s = novo('Introdução', 0, 'O fenómeno tem escala: 17,6 milhões de utilizadores da Internet e 5,5 milhões de identidades em redes sociais. Dois episódios mostram o peso político: a campanha «2022 Vais Gostar», que passou das redes para a rua, e os protestos de Agosto de 2025. O problema para as estruturas de segurança é o volume: não é possível ler tudo, e as ferramentas comerciais não foram pensadas para o português de Angola.', 60);
    s.addText('Milhões de angolanos nas redes, poucos analistas para as ler', { placeholder: 'title' });
    const stats = [['17,6 M', 'utilizadores da Internet', '44,8% da população'], ['5,50 M', 'identidades em redes sociais', '14,0% da população'], ['30,6 M', 'ligações móveis', 'o telemóvel é o acesso principal']];
    stats.forEach(([v, l, d], i) => {
      const x = MX + i * 2.55;
      cartao(s, x, 1.95, 2.35, 2.6, `estatistica-${i + 1}`);
      s.addText(v, { x: x + 0.15, y: 2.15, w: 2.05, h: 0.9, fontSize: 38, bold: true, color: i === 1 ? RED : NAVY, margin: 0, isTextBox: true });
      s.addText([{ text: l, options: { bold: true, breakLine: true } }, { text: d, options: { color: GREY } }], { x: x + 0.15, y: 3.1, w: 2.05, h: 1.2, fontSize: 14, color: C.text1, margin: 0, valign: 'top', isTextBox: true });
    });
    s.addText('Fonte: Kemp (2025), dados de Outubro de 2025.', { x: MX, y: 4.65, w: 7.5, h: 0.3, fontSize: 10, italic: true, color: GREY, margin: 0, isTextBox: true });
    s.addText([
      { text: 'Da rede para a rua', options: { bold: true, fontSize: 18, color: NAVY, breakLine: true } },
      { text: 'A campanha «2022 Vais Gostar» começou nas redes e terminou em manifestações em várias províncias (Hassane, 2021).', options: { bullet: true, breakLine: true } },
      { text: 'Nos protestos de Agosto de 2025 circularam conteúdos sintéticos para influenciar a narrativa (Cintra, 2025).', options: { bullet: true, breakLine: true } },
      { text: 'O limite é humano: há mais publicações do que analistas, e as ferramentas comerciais não foram feitas para o português de Angola.', options: { bullet: true } },
    ], { x: 8.45, y: 1.95, w: 4.3, h: 3.6, fontSize: 14, color: C.text1, margin: 0, valign: 'top', paraSpaceAfter: 8, isTextBox: true });
    circulo(s, MX, 5.35, 0.75, ic.lupa);
    s.addText('Ideia central: um sistema que ajude o analista a decidir o que ler primeiro, sem decidir por ele.', { x: MX + 1, y: 5.35, w: 11, h: 0.75, fontSize: 16, bold: true, color: NAVY, valign: 'middle', margin: 0, isTextBox: true });
  }

  // ============================================================ 4. Problema e hipóteses
  {
    const s = novo('Introdução', 0, 'A pergunta de partida e as quatro hipóteses, cada uma com critério quantitativo. H1 compara algoritmos; H2 mede tempo; H3 antecedência; H4 a queda em conteúdo angolano. Ler devagar a pergunta.', 60);
    s.addText('Pergunta de partida e hipóteses', { placeholder: 'title' });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 1.85, w: W - 2 * MX, h: 1.1, rectRadius: 0.08, fill: { color: NAVY }, line: { color: NAVY }, objectName: 'pergunta' });
    s.addText('Em que medida um sistema baseado em aprendizagem automática consegue apoiar, de forma fiável e juridicamente responsável, a triagem de publicações ameaçadoras em redes sociais angolanas?',
      { x: MX + 0.3, y: 1.85, w: W - 2 * MX - 0.6, h: 1.1, fontSize: 17, italic: true, color: 'FFFFFF', valign: 'middle', margin: 0, isTextBox: true });
    const hip = [
      ['H1', 'Os modelos profundos superam os clássicos', 'ΔF1-macro ≥ 5 p.p. e p < 0,05 (McNemar com Bonferroni)'],
      ['H2', 'Cada publicação é processada em menos de 60 s', 'Importação, anonimização, classificação e entrada na fila'],
      ['H3', 'Antecedência de pelo menos 48 horas', 'Face a eventos de segurança documentados'],
      ['H4', 'O desempenho cai em conteúdo angolano', 'ΔF1-macro ≥ 5 p.p. face aos corpora públicos'],
    ];
    hip.forEach(([c, t, d], i) => {
      const col = i % 2, lin = Math.floor(i / 2);
      const x = MX + col * 6.15, y = 3.25 + lin * 1.55;
      cartao(s, x, y, 5.95, 1.35, `hipotese-${c}`);
      s.addText(c, { x: x + 0.2, y: y + 0.2, w: 0.9, h: 0.95, fontSize: 28, bold: true, color: RED, valign: 'middle', margin: 0, isTextBox: true });
      s.addText([{ text: t, options: { bold: true, fontSize: 16, color: NAVY, breakLine: true } }, { text: d, options: { fontSize: 13, color: C.text1 } }],
        { x: x + 1.15, y: y + 0.15, w: 4.6, h: 1.05, valign: 'middle', margin: 0, isTextBox: true });
    });
  }

  // ============================================================ Objectivos
  {
    const s = novo('Introdução', 0, 'O objectivo geral e os cinco objectivos específicos. Ligar cada um à hipótese que o testa: OE2 com a H1, OE3 com a H4, OE4 com a H2 e a H3. O OE1 (corpus) e o OE5 (quadro ético e legal) não têm hipótese: são de construção e normativos.', 45);
    s.addText('Objectivos: um sistema que se mede antes de se usar', { placeholder: 'title' });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 1.85, w: W - 2 * MX, h: 1.2, rectRadius: 0.08, fill: { color: NAVY }, line: { color: NAVY }, objectName: 'objectivo-geral' });
    s.addText([{ text: 'Objectivo geral  ', options: { bold: true, color: GOLD } }, { text: 'Desenvolver e avaliar um sistema de apoio à triagem de publicações ameaçadoras em redes sociais angolanas, que combine um classificador adaptado ao português com revisão humana obrigatória e protecção de dados desde a concepção.', options: { color: 'FFFFFF' } }],
      { x: MX + 0.3, y: 1.85, w: W - 2 * MX - 0.6, h: 1.2, fontSize: 15, valign: 'middle', margin: 0, isTextBox: true });
    const oes = [
      ['OE1', 'Construir um corpus angolano anotado por três anotadores, com proveniência registada', '—'],
      ['OE2', 'Comparar SVM, Floresta Aleatória, Bi-LSTM e BERTimbau com testes estatísticos', 'H1'],
      ['OE3', 'Quantificar a perda de desempenho em conteúdo angolano e as suas causas', 'H4'],
      ['OE4', 'Desenvolver o protótipo de triagem e o protocolo da sua avaliação', 'H2, H3'],
      ['OE5', 'Propor um quadro de uso responsável conforme a Lei n.º 22/11', '—'],
    ];
    const gw = (W - 2 * MX - 4 * 0.15) / 5;
    oes.forEach(([c, t, h], i) => {
      const x = MX + i * (gw + 0.15);
      cartao(s, x, 3.3, gw, 3.0, `objectivo-${c}`);
      s.addText(c, { x: x + 0.2, y: 3.45, w: gw - 0.4, h: 0.5, fontSize: 22, bold: true, color: RED, margin: 0, isTextBox: true });
      s.addText(t, { x: x + 0.2, y: 4.0, w: gw - 0.4, h: 1.6, fontSize: 15, color: C.text1, margin: 0, valign: 'top', isTextBox: true });
      s.addText(h === '—' ? 'sem hipótese' : `testado por ${h}`, { x: x + 0.2, y: 5.75, w: gw - 0.4, h: 0.35, fontSize: 12, bold: h !== '—', color: h === '—' ? GREY : NAVY, margin: 0, isTextBox: true });
    });
  }

  // ============================================================ Revisão da literatura
  pres.addSection({ title: 'Revisão da literatura' });
  {
    const s = novo('Revisão da literatura', 1, 'Três conclusões da literatura. Os sistemas internacionais (MediFor, Palantir, EU DisinfoLab) não estão disponíveis ou criam dependência externa. Os recursos de PLN em português são brasileiros, e a desinformação vem de notícias completas. Os classificadores generalizam mal entre domínios e variedades, e manter um humano no circuito exige contramedidas contra o viés de automação.', 75);
    s.addText('A literatura deixa uma lacuna para Angola', { placeholder: 'title' });
    const cards = [
      [ic.globo, 'Sistemas existentes', 'Programas e plataformas internacionais sem português de Angola ou com dependência de fornecedores externos (Defense Advanced Research Projects Agency, 2016; Palantir Technologies, 2021).'],
      [ic.livro, 'Recursos brasileiros', 'BERTimbau, ToLD-BR, HateBR e Fake.br são brasileiros; a desinformação disponível são notícias completas (Souza et al., 2020; Monteiro et al., 2018).'],
      [ic.rede, 'Generalização fraca', 'Os classificadores de conteúdo nocivo perdem desempenho fora do domínio de treino e aprendem atalhos (Fortuna et al., 2021; Geirhos et al., 2020).'],
      [ic.utilizador, 'O humano no circuito', 'Rever não basta: complacência e viés de automação exigem revisão cega e amostras de controlo (Parasuraman & Manzey, 2010).'],
    ];
    cards.forEach(([img, t, d], i) => {
      const x = MX + i * 3.08;
      cartao(s, x, 1.9, 2.9, 3.85, `lacuna-${i + 1}`);
      circulo(s, x + 0.25, 2.15, 0.8, img, i === 2 ? RED : NAVY);
      s.addText(t, { x: x + 0.25, y: 3.1, w: 2.45, h: 0.45, fontSize: 16, bold: true, color: NAVY, margin: 0, isTextBox: true });
      s.addText(d, { x: x + 0.25, y: 3.55, w: 2.45, h: 2.05, fontSize: 13, color: C.text1, margin: 0, valign: 'top', isTextBox: true });
    });
    s.addText('Lacuna: não existe uma medida do desempenho destes modelos em conteúdo angolano, nem um sistema de triagem desenhado em função das suas limitações.',
      { x: MX, y: 6.0, w: W - 2 * MX, h: 0.55, fontSize: 15, bold: true, color: RED, margin: 0, valign: 'middle', isTextBox: true });
  }

  // ============================================================ 6. Desenho
  pres.addSection({ title: 'Metodologia' });
  {
    const s = novo('Metodologia', 2, 'Paradigma pragmático e aplicado, abordagem quantitativa. Três fases: dados, modelos e sistema. As revisões feitas no sistema podem voltar a alimentar o treino.', 45);
    s.addText('Investigação em três fases: dados, modelos e sistema', { placeholder: 'title' });
    s.addImage({ path: 'fig3_1_desenho.png', x: 1.6, y: 1.8, w: 7.55, h: 4.51, objectName: 'figura-desenho' });
    legenda(s, 'Figura 1 – Desenho da investigação', 1.6, 6.35, 7.55);
    s.addText([
      { text: 'Paradigma', options: { bold: true, color: NAVY, breakLine: true } },
      { text: 'Pragmático e aplicado; abordagem quantitativa', options: { breakLine: true } },
      { text: ' ', options: { breakLine: true, fontSize: 8 } },
      { text: 'Testes', options: { bold: true, color: NAVY, breakLine: true } },
      { text: 'H1 e H4 com métricas e testes estatísticos; H2 e H3 com o sistema em funcionamento', options: { breakLine: true } },
      { text: ' ', options: { breakLine: true, fontSize: 8 } },
      { text: 'Ética', options: { bold: true, color: NAVY, breakLine: true } },
      { text: 'Só conteúdo público, anonimização à entrada, Lei n.º 22/11', options: {} },
    ], { x: 9.55, y: 1.95, w: 3.2, h: 4.2, fontSize: 14, color: C.text1, margin: 0, valign: 'top', isTextBox: true });
  }

  // ============================================================ 7. Corpus angolano
  {
    const s = novo('Metodologia', 2, 'O corpus angolano: 2 637 publicações públicas, sobretudo comentários do YouTube pela interface oficial, anotadas por três anotadores com κ de Fleiss de 0,718, acordo substancial. Nos desacordos, prevalece a categoria mais grave. Notar que a Mobilização Hostil só existe no piloto.', 60);
    s.addText('Corpus angolano: 2 637 publicações e três anotadores', { placeholder: 'title' });
    s.addChart(pres.charts.DOUGHNUT, [{ name: 'Publicações', labels: ['Normal', 'Mobilização Hostil', 'Desinformação', 'Discurso de Ódio'], values: [1664, 364, 326, 283] }], {
      x: MX, y: 1.75, w: 5.6, h: 4.45, holeSize: 55, chartColors: ['8FA3B8', RED, GOLD, BLUE],
      showLegend: true, legendPos: 'r', legendFontSize: 12, legendFontFace: '+mn-lt', legendColor: '1B2733',
      showValue: true, showPercent: false, dataLabelColor: 'FFFFFF', dataLabelFontSize: 11, dataLabelFontFace: '+mn-lt',
      showTitle: false, objectName: 'grafico-corpus',
    });
    legenda(s, 'Figura 2 – Distribuição das etiquetas finais do corpus angolano', MX, 6.25, 5.6);
    cartao(s, 6.65, 1.9, 2.6, 2.1, 'kappa');
    s.addText([{ text: '0,718', options: { fontSize: 40, bold: true, color: NAVY, breakLine: true } }, { text: 'κ de Fleiss: acordo substancial', options: { fontSize: 13, color: C.text1 } }],
      { x: 6.85, y: 2.0, w: 2.25, h: 1.9, margin: 0, valign: 'middle', isTextBox: true });
    cartao(s, 9.45, 1.9, 3.28, 2.1, 'origem');
    s.addText([{ text: '86%', options: { fontSize: 40, bold: true, color: NAVY, breakLine: true } }, { text: 'comentários do YouTube pela interface oficial', options: { fontSize: 13, color: C.text1 } }],
      { x: 9.65, y: 2.0, w: 2.95, h: 1.9, margin: 0, valign: 'middle', isTextBox: true });
    s.addText([
      { text: 'Autores anonimizados antes de gravar (pseudónimo HMAC)', options: { bullet: true, breakLine: true } },
      { text: 'Desacordo: prevalece a categoria mais grave; 11,3% das ameaças vêm de um só voto', options: { bullet: true, breakLine: true } },
      { text: 'Lotes enriquecidos por tema e por léxico usados só no treino', options: { bullet: true } },
    ], { x: 6.65, y: 4.25, w: 6.1, h: 1.9, fontSize: 14, color: C.text1, margin: 0, paraSpaceAfter: 6, valign: 'top', isTextBox: true });
  }

  // ============================================================ 8. Corpus híbrido e modelos
  {
    const s = novo('Metodologia', 2, 'O piloto, por si só, é pequeno. Juntou-se a três corpora públicos brasileiros, num total de 26 859 registos. Quatro modelos de três gerações. Protocolo definido antes de ver o teste: F1-macro com IC por bootstrap e McNemar com Bonferroni. Atenção: 91% do teste é brasileiro, por isso a H4 separa os dois domínios.', 60);
    s.addText('Corpus híbrido de 26 859 registos e quatro modelos comparados', { placeholder: 'title' });
    s.addText('Tabela 1 – Composição do corpus híbrido por fonte', { x: MX, y: 1.8, w: 6, h: 0.3, fontSize: 11, bold: true, color: C.text1, align: 'center', margin: 0, isTextBox: true });
    const cab = { bold: true, color: 'FFFFFF', fill: { color: NAVY }, fontSize: 13, align: 'center' };
    const lin = (a, b, c, op = {}) => [{ text: a, options: { align: 'left', ...op } }, { text: b, options: { align: 'center', ...op } }, { text: c, options: { align: 'right', ...op } }];
    s.addTable([
      [{ text: 'Fonte', options: { ...cab, align: 'left' } }, { text: 'Origem', options: cab }, { text: 'Registos', options: { ...cab, align: 'right' } }],
      lin('ToLD-BR', 'Twitter, Brasil', '12 709'), lin('Fake.br', 'Notícias, Brasil', '7 199'), lin('HateBR', 'Instagram, Brasil', '4 378'),
      lin('Piloto angolano', 'YouTube e outros, Angola', '2 573', { bold: true, color: RED }),
      lin('Total', '', '26 859', { bold: true }),
    ], { x: MX, y: 2.15, w: 6, colW: [1.9, 2.6, 1.5], fontSize: 13, color: '1B2733', border: { type: 'solid', pt: 0.5, color: LINE }, rowH: 0.42, objectName: 'tabela-corpus' });
    s.addText('Nota: valores após deduplicação. Divisão estratificada 70/15/15; teste com 3 987 itens.', { x: MX, y: 4.8, w: 6, h: 0.3, fontSize: 10, italic: true, color: GREY, margin: 0, isTextBox: true });
    const mod = [['SVM', 'TF-IDF', '8FA3B8'], ['Floresta Aleatória', 'TF-IDF', '8FA3B8'], ['Bi-LSTM', 'Sequência', BLUE], ['BERTimbau', 'Transformer pré-treinado', NAVY]];
    mod.forEach(([n, r, cor], i) => {
      const y = 1.85 + i * 0.82;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.1, y, w: 5.63, h: 0.68, rectRadius: 0.08, fill: { color: cor }, line: { color: cor }, objectName: `modelo-${i + 1}` });
      s.addText([{ text: n, options: { bold: true, fontSize: 16 } }, { text: `   ${r}`, options: { fontSize: 13 } }], { x: 7.3, y, w: 5.3, h: 0.68, color: 'FFFFFF', valign: 'middle', margin: 0, isTextBox: true });
    });
    s.addText([
      { text: 'Protocolo fixado antes do teste', options: { bold: true, color: NAVY, breakLine: true } },
      { text: 'F1-macro com IC 95% por bootstrap; McNemar com correcção de Bonferroni; variantes escolhidas na validação.', options: {} },
    ], { x: 7.1, y: 5.2, w: 5.63, h: 1.1, fontSize: 14, color: C.text1, margin: 0, valign: 'top', isTextBox: true });
  }

  // ============================================================ 9. Comparação de modelos
  pres.addSection({ title: 'Resultados' });
  {
    const s = novo('Resultados', 3, 'O BERTimbau obteve F1-macro de 0,807, com intervalo que não se sobrepõe aos outros; a diferença é de 14,6 a 17,4 p.p., com p < 10^-47. O Bi-LSTM não se distingue da Floresta Aleatória: por isso a H1 fica parcialmente confirmada. A explicação provável é o pré-treino.', 60);
    s.addText('O BERTimbau supera os restantes modelos em 15 a 17 pontos', { placeholder: 'title' });
    s.addChart(pres.charts.BAR, [{ name: 'F1-macro', labels: ['SVM', 'Floresta Aleatória', 'Bi-LSTM', 'BERTimbau'], values: [0.633, 0.659, 0.660, 0.807] }], {
      x: MX, y: 1.75, w: 7.4, h: 4.5, barDir: 'col', chartColors: ['8FA3B8', '8FA3B8', BLUE, NAVY], valAxisMinVal: 0, valAxisMaxVal: 1,
      valAxisLabelFormatCode: '0.0', dataLabelFormatCode: '0.000', showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 14, dataLabelFontBold: true, dataLabelColor: '1B2733', dataLabelFontFace: '+mn-lt',
      catAxisLabelColor: '1B2733', valAxisLabelColor: '5B6B7F', catAxisLabelFontSize: 13, valAxisLabelFontSize: 11, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt',
      valGridLine: { color: 'E3E8EF', size: 0.5 }, catGridLine: { style: 'none' }, showLegend: false,
      showValAxisTitle: true, valAxisTitle: 'F1-macro (teste, n = 3 987)', valAxisTitleFontSize: 11, valAxisTitleColor: '5B6B7F', valAxisTitleFontFace: '+mn-lt',
      objectName: 'grafico-modelos',
    });
    legenda(s, 'Figura 3 – F1-macro dos quatro modelos no conjunto de teste', MX, 6.3, 7.4);
    cartao(s, 8.4, 1.9, 4.33, 1.45, 'ic');
    s.addText([{ text: '0,807', options: { fontSize: 34, bold: true, color: NAVY, breakLine: true } }, { text: 'BERTimbau, IC 95% de 0,774 a 0,838', options: { fontSize: 13 } }], { x: 8.6, y: 1.95, w: 4, h: 1.35, margin: 0, valign: 'middle', color: C.text1, isTextBox: true });
    cartao(s, 8.4, 3.55, 4.33, 1.25, 'mcnemar');
    s.addText([{ text: 'p < 10⁻⁴⁷', options: { fontSize: 26, bold: true, color: NAVY, breakLine: true } }, { text: 'McNemar com Bonferroni, nos três pares', options: { fontSize: 13 } }], { x: 8.6, y: 3.6, w: 4, h: 1.15, margin: 0, valign: 'middle', color: C.text1, isTextBox: true });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.4, y: 5.0, w: 4.33, h: 1.2, rectRadius: 0.08, fill: { color: 'FBE9EC' }, line: { color: 'FBE9EC' }, objectName: 'h1' });
    s.addText([{ text: 'H1 parcialmente confirmada', options: { bold: true, color: RED, breakLine: true } }, { text: 'O Bi-LSTM não se distingue da Floresta Aleatória', options: {} }], { x: 8.6, y: 5.05, w: 4, h: 1.1, fontSize: 14, color: C.text1, margin: 0, valign: 'middle', isTextBox: true });
  }

  // ============================================================ 10. H4
  {
    const s = novo('Resultados', 3, 'Este é o resultado central. No corpus público o F1-macro é 0,919; no piloto angolano cai para 0,533: 38,6 pontos. A maior queda é na Desinformação, de 0,99 para 0,24: o modelo aprendeu o estilo das notícias do Fake.br, não o fenómeno. A estimativa realista para Angola é 0,53, e é essa que o sistema mostra ao analista.', 60);
    s.addText('Em conteúdo angolano o F1-macro cai 38,6 pontos (H4)', { placeholder: 'title' });
    s.addChart(pres.charts.BAR, [
      { name: 'Corpus público (n = 3 632)', labels: ['Normal', 'Desinformação', 'Discurso de Ódio', 'Mobilização Hostil'], values: [0.963, 0.992, 0.802, 0] },
      { name: 'Piloto angolano (n = 355)', labels: ['Normal', 'Desinformação', 'Discurso de Ódio', 'Mobilização Hostil'], values: [0.825, 0.235, 0.518, 0.554] },
    ], {
      x: MX, y: 1.75, w: 7.6, h: 4.5, barDir: 'col', barGrouping: 'clustered', chartColors: [BLUE, RED], valAxisMinVal: 0, valAxisMaxVal: 1,
      valAxisLabelFormatCode: '0.0', dataLabelFormatCode: '0.00;;;', showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 12, dataLabelColor: '1B2733', dataLabelFontFace: '+mn-lt',
      catAxisLabelColor: '1B2733', valAxisLabelColor: '5B6B7F', catAxisLabelFontSize: 12, valAxisLabelFontSize: 11, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt',
      valGridLine: { color: 'E3E8EF', size: 0.5 }, catGridLine: { style: 'none' }, showLegend: true, legendPos: 't', legendFontSize: 12, legendFontFace: '+mn-lt', legendColor: '1B2733',
      objectName: 'grafico-h4',
    });
    legenda(s, 'Figura 4 – F1 do BERTimbau por categoria: corpus público e piloto angolano', MX, 6.3, 7.6, 'Nota: o corpus público não tem Mobilização Hostil.');
    cartao(s, 8.55, 1.9, 4.18, 1.7, 'queda');
    s.addText([{ text: '0,919 → 0,533', options: { fontSize: 30, bold: true, color: RED, breakLine: true } }, { text: 'F1-macro: público → angolano (IC sem sobreposição)', options: { fontSize: 13 } }], { x: 8.75, y: 1.95, w: 3.9, h: 1.6, margin: 0, valign: 'middle', color: C.text1, isTextBox: true });
    s.addText([
      { text: 'Desinformação: 0,99 → 0,24', options: { bold: true, color: NAVY, breakLine: true } },
      { text: 'O modelo aprendeu o estilo das notícias do Fake.br, não o fenómeno (aprendizagem de atalhos).', options: { breakLine: true } },
      { text: ' ', options: { breakLine: true, fontSize: 6 } },
      { text: 'H4 confirmada, com reservas', options: { bold: true, color: RED, breakLine: true } },
      { text: 'Piloto pequeno (n = 355); não separa língua, plataforma e registo.', options: {} },
    ], { x: 8.55, y: 3.85, w: 4.18, h: 2.4, fontSize: 14, color: C.text1, margin: 0, valign: 'top', isTextBox: true });
  }

  // ============================================================ 11. Ordenação da fila
  {
    const O = JSON.parse(fs.readFileSync('ordenacao.json', 'utf8'));
    const pts = (k) => O[k].curva.filter((_, i) => i % 10 === 0).map((v) => Math.round(v * 1000) / 10);
    const labels = ['0%', '10%', '20%', '30%', '40%', '50%', '60%', '70%', '80%', '90%', '100%'];
    const s = novo('Resultados', 3, 'Como o sistema usa as probabilidades para ordenar a fila, medi também o esforço de revisão. Com o BERTimbau, rever um quarto da fila encontra 80% das ameaças. Mas a ordem reflecte a confiança e não a gravidade: a Mobilização Hostil fica a meio da fila. E 11,8% das ameaças ficam entre os itens que o modelo considera Normais: é isso que justifica a amostra de controlo.', 50);
    s.addText('A fila encontra 80% das ameaças em 25% da leitura', { placeholder: 'title' });
    s.addChart(pres.charts.LINE, [
      { name: 'BERTimbau', labels, values: pts('BERTimbau') },
      { name: 'Bi-LSTM', labels, values: pts('Bi-LSTM') },
      { name: 'Floresta Aleatória', labels, values: pts('Floresta Aleatória') },
      { name: 'Ordem aleatória', labels, values: labels.map((_, i) => i * 10) },
    ], {
      x: MX, y: 1.75, w: 7.6, h: 4.5, chartColors: [NAVY, BLUE, GOLD, 'B8C4D1'], lineSize: 2.5, lineDataSymbol: 'none',
      valAxisMinVal: 0, valAxisMaxVal: 100, valAxisLabelFormatCode: '0"%"',
      catAxisLabelColor: '1B2733', valAxisLabelColor: '5B6B7F', catAxisLabelFontSize: 11, valAxisLabelFontSize: 11, catAxisLabelFontFace: '+mn-lt', valAxisLabelFontFace: '+mn-lt',
      valGridLine: { color: 'E3E8EF', size: 0.5 }, catGridLine: { style: 'none' }, showLegend: true, legendPos: 'b', legendFontSize: 12, legendFontFace: '+mn-lt', legendColor: '1B2733',
      showValAxisTitle: true, valAxisTitle: 'Ameaças encontradas', valAxisTitleFontSize: 11, valAxisTitleColor: '5B6B7F', valAxisTitleFontFace: '+mn-lt',
      showCatAxisTitle: true, catAxisTitle: 'Fracção da fila revista, por prioridade', catAxisTitleFontSize: 11, catAxisTitleColor: '5B6B7F', catAxisTitleFontFace: '+mn-lt',
      objectName: 'grafico-esforco',
    });
    legenda(s, 'Figura 5 – Curva de esforço de revisão no conjunto de teste', MX, 6.3, 7.6);
    const pts2 = [['25%', 'da fila revista encontra 80% das ameaças (BERTimbau)', NAVY], ['927.ª', 'posição mediana da Mobilização Hostil: a ordem segue a confiança, não a gravidade', RED], ['11,8%', 'das ameaças ficam entre os Normais: daí a amostra de controlo', GOLD]];
    pts2.forEach(([v, t, cor], i) => {
      const y = 1.85 + i * 1.5;
      cartao(s, 8.55, y, 4.18, 1.35, `ponto-${i + 1}`);
      s.addText(v, { x: 8.7, y, w: 1.45, h: 1.35, fontSize: 26, bold: true, color: cor === GOLD ? '9A7400' : cor, valign: 'middle', margin: 0, isTextBox: true });
      s.addText(t, { x: 10.2, y, w: 2.4, h: 1.35, fontSize: 12, color: C.text1, valign: 'middle', margin: 0, isTextBox: true });
    });
  }

  // ============================================================ 12. H2
  {
    const s = novo('Resultados', 3, 'A H2 foi medida com o protótipo num computador modesto, sem GPU: 0,63 segundos por publicação. Com a gravação por sublotes, as primeiras publicações chegam à fila em 36 segundos, e todas em menos de 60 segundos em recolhas até cerca de 64 publicações. A H3 não pôde ser testada por falta de um corpus datado.', 45);
    s.addText('Cada publicação é processada em 0,63 s, sem GPU (H2)', { placeholder: 'title' });
    const st = [['0,63 s', 'por publicação: importação, anonimização, classificação e gravação', ic.relogio], ['36 s', 'até as primeiras publicações chegarem à fila, com gravação por sublotes', ic.grafico], ['≤ 64', 'publicações por recolha para todas chegarem em menos de 60 s', ic.monitor]];
    st.forEach(([v, t, img], i) => {
      const x = MX + i * 4.1;
      cartao(s, x, 1.95, 3.9, 2.9, `h2-${i + 1}`);
      circulo(s, x + 0.25, 2.2, 0.75, img);
      s.addText(v, { x: x + 0.25, y: 3.05, w: 3.4, h: 0.8, fontSize: 36, bold: true, color: NAVY, margin: 0, isTextBox: true });
      s.addText(t, { x: x + 0.25, y: 3.85, w: 3.4, h: 0.85, fontSize: 13, color: C.text1, margin: 0, valign: 'top', isTextBox: true });
    });
    s.addText('Ensaio: 198 comentários reais, 3 repetições, processador Intel N100 com 8 GB de RAM.', { x: MX, y: 5.0, w: 12, h: 0.3, fontSize: 11, italic: true, color: GREY, margin: 0, isTextBox: true });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 5.5, w: 5.95, h: 0.85, rectRadius: 0.08, fill: { color: 'E6F2EC' }, line: { color: 'E6F2EC' }, objectName: 'h2-decisao' });
    s.addText([{ text: 'H2: confirmada com condições', options: { bold: true, color: GREEN } }], { x: MX + 0.25, y: 5.5, w: 5.6, h: 0.85, fontSize: 16, valign: 'middle', margin: 0, isTextBox: true });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.78, y: 5.5, w: 5.95, h: 0.85, rectRadius: 0.08, fill: { color: LIGHT }, line: { color: LIGHT }, objectName: 'h3-decisao' });
    s.addText([{ text: 'H3: não testada', options: { bold: true, color: GREY } }, { text: ' (sem corpus datado em torno de eventos)', options: { color: C.text1 } }], { x: 7.03, y: 5.5, w: 5.6, h: 0.85, fontSize: 14, valign: 'middle', margin: 0, isTextBox: true });
  }

  // ============================================================ Limitações
  {
    const s = novo('Resultados', 3, 'Antes do sistema, digo o que os resultados não permitem afirmar. O piloto é pequeno, sobretudo na Mobilização Hostil (47 exemplos de teste). 91% do teste é brasileiro. A desinformação disponível são notícias. Não separei língua, plataforma e registo. A utilidade para analistas e a antecipação não foram medidas. E o protótipo não teve auditoria de segurança independente.', 55);
    s.addText('O que estes resultados não permitem afirmar', { placeholder: 'title' });
    const lims = [
      [ic.bd, 'Piloto pequeno', '355 itens de teste; a Mobilização Hostil tem 47, com IC do F1 de 0,42 a 0,66'],
      [ic.globo, 'Teste dominado pelo Brasil', '91% do teste é brasileiro; para Angola, a estimativa é 0,53'],
      [ic.livro, 'Desinformação em notícias', 'A única fonte pública são notícias completas, não comentários'],
      [ic.lupa, 'Causas não separadas', 'Língua, plataforma e registo variam ao mesmo tempo no piloto'],
      [ic.utilizador, 'Uso real por medir', 'Utilidade da fila com analistas e antecipação (H3) por avaliar'],
      [ic.escudo, 'Segurança sem auditoria', 'Boas práticas seguidas, mas sem testes de intrusão independentes'],
    ];
    lims.forEach(([img, t, d], i) => {
      const col = i % 3, lin = Math.floor(i / 3);
      const cw = (W - 2 * MX - 2 * 0.2) / 3, x = MX + col * (cw + 0.2), y = 1.9 + lin * 2.25;
      cartao(s, x, y, cw, 2.05, `limitacao-${i + 1}`);
      circulo(s, x + 0.25, y + 0.25, 0.65, img, i === 4 ? RED : NAVY);
      s.addText(t, { x: x + 1.05, y: y + 0.25, w: cw - 1.25, h: 0.65, fontSize: 16, bold: true, color: NAVY, valign: 'middle', margin: 0, isTextBox: true });
      s.addText(d, { x: x + 0.25, y: y + 1.05, w: cw - 0.5, h: 0.85, fontSize: 13, color: C.text1, valign: 'top', margin: 0, isTextBox: true });
    });
    s.addText('Fonte: Secção 5.4 da dissertação.', { x: MX, y: 6.45, w: 6, h: 0.3, fontSize: 10, italic: true, color: GREY, margin: 0, isTextBox: true });
  }

  // ============================================================ 13. Arquitectura
  pres.addSection({ title: 'Sistema' });
  {
    const s = novo('Sistema', 4, 'Os resultados ditaram o desenho: o modelo não decide, ordena. Arquitectura leve, num único servidor, software livre e sem dependência da Internet. Salvaguardas: anonimização à entrada, sem perfis, revisão humana obrigatória, auditoria. Passo agora para a demonstração.', 60);
    s.addText('Arquitectura leve, num único servidor, com o analista no centro', { placeholder: 'title' });
    s.addImage({ path: 'fig3_3_arquitectura.png', x: MX, y: 1.75, w: 5.67, h: 4.46, objectName: 'figura-arquitectura' });
    legenda(s, 'Figura 6 – Arquitectura em camadas do sistema', MX, 6.3, 5.67);
    const sal = [
      [ic.cadeado, 'Anonimização à entrada', 'Pseudónimo HMAC; telefones, endereços e menções mascarados'],
      [ic.olho, 'Sem perfis de pessoas', 'Publicações e agregados por categoria, período e província'],
      [ic.utilizador, 'Decisão sempre humana', 'Fila por analista, revisão cega e amostra de controlo'],
      [ic.escudo, 'Contas e auditoria', 'Palavras-passe derivadas, recuperação sem e-mail, tudo registado'],
      [ic.wifi, 'Funciona sem Internet', 'Sem bibliotecas nem serviços externos; recolha automática'],
      [ic.teste, '121 testes automáticos', 'Todos aprovados na versão final'],
    ];
    sal.forEach(([img, t, d], i) => {
      const y = 1.8 + i * 0.75;
      circulo(s, 6.75, y + 0.04, 0.58, img, i === 2 ? RED : NAVY);
      s.addText([{ text: t, options: { bold: true, color: NAVY, fontSize: 14, breakLine: true } }, { text: d, options: { fontSize: 12, color: C.text1 } }],
        { x: 7.5, y, w: 5.23, h: 0.68, margin: 0, valign: 'middle', isTextBox: true });
    });
  }

  // ============================================================ 14. Demonstração
  {
    const s = novo('Sistema', 4, 'ANTES DA SESSÃO: arrancar o servidor com «python uan.py servir --demonstracao», entrar como demo.analista num separador e como demo.supervisor noutro. Ao chegar a este diapositivo, mudar para o navegador (Alt+Tab).\n\nRoteiro com tempos:\n1) Panorama (0:25): o que foi recolhido e sinalizado.\n2) Fila e amostra de controlo (1:00): ler uma publicação, decidir com a tecla, desfazer com U; mostrar as probabilidades e o realce do lugar; referir a revisão cega; abrir a amostra de controlo.\n3) Alertas e mapa (1:00): sino, mapa com cartão de uma província, reprodução semana a semana.\n4) Sobre o modelo (0:30): o desempenho em Angola, 0,53, está à vista do analista.\n5) Fontes e contas (0:40): recolha automática com a estimativa da quota; ligação «Esqueceu-se da palavra-passe?» e pedido ao supervisor.\nPassagens para o navegador e de regresso: 0:25.\n\nSe a demonstração falhar, usar os diapositivos de reserva A, B e C, no fim.', 240);
    s.addText('Demonstração do sistema', { placeholder: 'title' });
    const passos = [
      ['1', 'Panorama', 'O que foi recolhido e o que o modelo sinalizou', '0:25'],
      ['2', 'Fila e amostra de controlo', 'Decidir com as teclas 1 a 4, desfazer, revisão cega', '1:00'],
      ['3', 'Alertas e mapa', 'Sino em tempo real, mapa por província, evolução semanal', '1:00'],
      ['4', 'Sobre o modelo', 'O desempenho em Angola visível para o analista', '0:30'],
      ['5', 'Fontes e contas', 'Recolha automática, quota do YouTube, recuperação do acesso', '0:40'],
    ];
    passos.forEach(([n, t, d, m], i) => {
      const y = 1.8 + i * 0.86;
      s.addShape(pres.shapes.OVAL, { x: MX, y: y + 0.08, w: 0.6, h: 0.6, fill: { color: NAVY }, line: { color: NAVY } });
      s.addText(n, { x: MX, y: y + 0.08, w: 0.6, h: 0.6, fontSize: 16, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0, isTextBox: true });
      s.addText([{ text: t, options: { bold: true, color: NAVY, fontSize: 16, breakLine: true } }, { text: d, options: { fontSize: 13, color: C.text1 } }],
        { x: MX + 0.8, y, w: 4.4, h: 0.76, margin: 0, valign: 'middle', isTextBox: true });
      s.addText(m, { x: MX + 5.2, y, w: 0.75, h: 0.76, fontSize: 15, bold: true, color: RED, align: 'right', valign: 'middle', margin: 0, isTextBox: true });
    });
    s.addImage({ path: 'fig3_7_painel.png', x: 7.15, y: 1.85, w: 5.58, h: 2.97, objectName: 'captura-fila' });
    legenda(s, 'Figura 7 – Fila de revisão no modo de demonstração', 7.15, 4.88, 5.58, 'Nota: dados fictícios e classificador simulado.');
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.15, y: 5.65, w: 5.58, h: 0.75, rectRadius: 0.08, fill: { color: NAVY }, line: { color: NAVY }, objectName: 'comando' });
    s.addText([{ text: 'python uan.py servir --demonstracao', options: { fontFace: 'Courier New', bold: true, color: GOLD, breakLine: true } }, { text: 'No navegador: http://127.0.0.1:8000', options: { color: 'FFFFFF', fontSize: 12 } }],
      { x: 7.35, y: 5.65, w: 5.3, h: 0.75, fontSize: 13, valign: 'middle', margin: 0, isTextBox: true });
    s.addText('Duração total: 4:00, incluindo 0:25 de passagem para o navegador e regresso.', { x: MX, y: 6.15, w: 6.2, h: 0.3, fontSize: 11, italic: true, color: GREY, margin: 0, isTextBox: true });
  }

  // ============================================================ 15. Hipóteses
  pres.addSection({ title: 'Conclusões' });
  {
    const s = novo('Conclusões', 5, 'Síntese das hipóteses. H1 parcialmente confirmada; H2 confirmada com condições; H3 não testada; H4 confirmada com reservas. Dizer com clareza o que não foi demonstrado: a utilidade da fila com analistas reais e a antecipação.', 55);
    s.addText('Verificação das hipóteses', { placeholder: 'title' });
    s.addText('Tabela 2 – Verificação formal das hipóteses de investigação', { x: MX, y: 1.75, w: W - 2 * MX, h: 0.3, fontSize: 11, bold: true, color: C.text1, align: 'center', margin: 0, isTextBox: true });
    const cab = { bold: true, color: 'FFFFFF', fill: { color: NAVY }, fontSize: 14 };
    const dec = (t, cor, fundo) => ({ text: t, options: { bold: true, color: cor, fill: { color: fundo }, align: 'center' } });
    s.addTable([
      [{ text: 'Hipótese', options: cab }, { text: 'Evidência', options: cab }, { text: 'Decisão', options: { ...cab, align: 'center' } }],
      ['H1. Modelos profundos superam os clássicos', 'BERTimbau +14,6 a +17,4 p.p., p < 10⁻⁴⁷; Bi-LSTM igual à Floresta Aleatória', dec('Parcialmente confirmada', '9A7400', 'FBF3DA')],
      ['H2. Menos de 60 s por publicação', '0,63 s em CPU; primeiras na fila em 36 s; todas em < 60 s até 64 por recolha', dec('Confirmada com condições', GREEN, 'E6F2EC')],
      ['H3. Antecedência ≥ 48 h', 'Sem corpus datado em torno de eventos nem divisão cronológica', dec('Não testada', GREY, LIGHT)],
      ['H4. Queda ≥ 5 p.p. em conteúdo angolano', 'F1-macro 0,919 → 0,533 (−38,6 p.p.); κ 0,88 → 0,44', dec('Confirmada, com reservas', RED, 'FBE9EC')],
    ], { x: MX, y: 2.1, w: W - 2 * MX, colW: [4.0, 5.3, 2.83], fontSize: 14, color: '1B2733', border: { type: 'solid', pt: 0.5, color: LINE }, rowH: [0.5, 0.85, 0.85, 0.85, 0.85], valign: 'middle', objectName: 'tabela-hipoteses' });
    s.addText('Fonte: Capítulo 4 da dissertação.', { x: MX, y: 6.15, w: 6, h: 0.3, fontSize: 10, italic: true, color: GREY, margin: 0, isTextBox: true });
  }

  // ============================================================ Conclusões e contributos
  {
    const s = novo('Conclusões', 5, 'Três conclusões e os quatro contributos. Mensagem central: o modelo ordena o trabalho, o analista decide; em Angola o desempenho realista é 0,53.', 45);
    s.addText('O modelo ordena o trabalho; o analista decide', { placeholder: 'title' });
    const conc = [
      'Só o BERTimbau serve como classificador principal, com vantagem estatisticamente sólida',
      'O desempenho não se transfere intacto para Angola: a estimativa realista é 0,53',
      'Um sistema de triagem com revisão humana, auditável e de baixo custo é viável com software livre',
    ];
    const contr = [
      'Primeiro corpus angolano anotado nestas quatro categorias',
      'Medida da lacuna de domínio, com intervalos de confiança',
      'Avaliação que inclui calibração e esforço de revisão',
      'Protótipo de código aberto com protecção de dados desde a concepção',
    ];
    cartao(s, MX, 1.85, 5.95, 4.45, 'conclusoes');
    s.addText('Conclusões', { x: MX + 0.3, y: 2.0, w: 5.4, h: 0.5, fontSize: 18, bold: true, color: NAVY, margin: 0, isTextBox: true });
    s.addText(conc.map((t, i) => ({ text: t, options: { bullet: { type: 'number' }, breakLine: i < conc.length - 1 } })),
      { x: MX + 0.3, y: 2.55, w: 5.4, h: 3.55, fontSize: 17, color: C.text1, margin: 0, valign: 'top', paraSpaceAfter: 10, isTextBox: true });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.78, y: 1.85, w: 5.95, h: 4.45, rectRadius: 0.08, fill: { color: NAVY }, line: { color: NAVY }, objectName: 'contributos' });
    s.addText('Contributos', { x: 7.08, y: 2.0, w: 5.4, h: 0.5, fontSize: 18, bold: true, color: GOLD, margin: 0, isTextBox: true });
    s.addText(contr.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < contr.length - 1 } })),
      { x: 7.08, y: 2.55, w: 5.4, h: 3.55, fontSize: 17, color: 'FFFFFF', margin: 0, valign: 'top', paraSpaceAfter: 10, isTextBox: true });
  }

  // ============================================================ Recomendações
  {
    const s = novo('Conclusões', 5, 'As recomendações, separadas das conclusões como pedem as Normas da UAN. As três primeiras são condições para qualquer uso institucional; as outras três são trabalho futuro. Fechar com: o investimento que mais rende são dados angolanos anotados.', 50);
    s.addText('Recomendações: validar primeiro, usar depois', { placeholder: 'title' });
    const grupos = [
      ['Condições para uso institucional', RED, [
        ['1', 'Avaliar a fila com analistas reais', 'Precisão no topo da fila, κ analista–sistema e amostra de controlo'],
        ['2', 'Obter parecer jurídico', 'Lei n.º 22/11, termos das plataformas e limites constitucionais'],
        ['3', 'Ampliar o corpus angolano', 'Medir sempre em Angola; mais Mobilização Hostil e Desinformação'],
      ]],
      ['Trabalho futuro', NAVY, [
        ['4', 'Substituir a fonte de desinformação', 'Publicações curtas, de preferência angolanas'],
        ['5', 'Adaptar o modelo ao domínio', 'Pré-treino com comentários angolanos; comparar com Albertina PT-PT'],
        ['6', 'Ordenar a fila por gravidade', 'Calibrar as probabilidades e aprender com a amostra de controlo'],
      ]],
    ];
    grupos.forEach(([g, cor, itens], gi) => {
      const x = MX + gi * 6.18;
      s.addText(g, { x, y: 1.8, w: 5.95, h: 0.4, fontSize: 15, bold: true, color: cor, margin: 0, isTextBox: true });
      itens.forEach(([n, t, d], i) => {
        const y = 2.3 + i * 1.3;
        cartao(s, x, y, 5.95, 1.15, `recomendacao-${n}`);
        s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.25, w: 0.65, h: 0.65, fill: { color: cor }, line: { color: cor } });
        s.addText(n, { x: x + 0.2, y: y + 0.25, w: 0.65, h: 0.65, fontSize: 18, bold: true, color: 'FFFFFF', align: 'center', valign: 'middle', margin: 0, isTextBox: true });
        s.addText([{ text: t, options: { bold: true, color: NAVY, fontSize: 15, breakLine: true } }, { text: d, options: { fontSize: 12.5, color: C.text1 } }],
          { x: x + 1.05, y: y + 0.1, w: 4.75, h: 0.95, margin: 0, valign: 'middle', isTextBox: true });
      });
    });
    s.addText('Fonte: Secção 5.7 da dissertação (nove recomendações; aqui as seis principais).', { x: MX, y: 6.3, w: 9, h: 0.3, fontSize: 10, italic: true, color: GREY, margin: 0, isTextBox: true });
  }

  // ============================================================ 17. Encerramento
  {
    const s = pres.addSlide({ masterName: 'ESCURO', sectionTitle: 'Conclusões' });
    nSlide += 1; tempos.push(15);
    s.addText('Obrigado pela atenção', { x: MX, y: 2.3, w: W - 2 * MX, h: 1.0, fontSize: 44, bold: true, color: 'FFFFFF', margin: 0, isTextBox: true });
    s.addText('Estou disponível para as perguntas e comentários do Júri', { x: MX, y: 3.35, w: W - 2 * MX, h: 0.6, fontSize: 20, color: GOLD, margin: 0, isTextBox: true });
    s.addText('Manuel Gonga Muinga · Mestrado em Engenharia e Ciência de Dados · Universidade Agostinho Neto, Faculdade de Engenharia · Luanda, 2026',
      { x: MX, y: 6.45, w: W - 2 * MX, h: 0.4, fontSize: 12, color: 'B8C4D1', margin: 0, isTextBox: true });
    s.addNotes('Tempo deste diapositivo: 0:15 (relógio no fim: 20:00 de 20:00).\n\nAgradecer e passar a palavra ao Presidente do Júri. Os diapositivos seguintes são de reserva, para a demonstração ou para as perguntas.');
  }

  // ============================================================ Reserva
  pres.addSection({ title: 'Reserva' });
  const reserva = [
    ['Reserva A – Fila de revisão', 'fig3_7_painel.png', 2720, 1450, 'Figura 8 – Fila de revisão: sugestão, probabilidades e decisão por teclado'],
    ['Reserva B – Mapa por província', 'fig3_8_mapa.png', 2360, 1834, 'Figura 9 – Mapa por província com cartão de Benguela (últimos 90 dias)'],
    ['Reserva C – Recuperação do acesso', 'fig3_12_recuperacao.png', 2520, 1870, 'Figura 10 – Recuperação do acesso sem correio electrónico'],
  ];
  reserva.forEach(([t, f, pw, ph, leg]) => {
    const s = pres.addSlide({ masterName: 'CONTEUDO', sectionTitle: 'Reserva' });
    agendaTopo(s, 4);
    s.addText(t, { placeholder: 'title' });
    const maxW = W - 2 * MX, maxH = 4.3;
    let w = maxW, h = w * ph / pw;
    if (h > maxH) { h = maxH; w = h * pw / ph; }
    s.addImage({ path: f, x: (W - w) / 2, y: 1.8, w, h, objectName: 'captura' });
    legenda(s, leg, MX, 1.85 + h, maxW, 'Nota: dados fictícios ou contas de exemplo; não descrevem pessoas reais.');
    s.addNotes('Diapositivo de reserva: usar se a demonstração ao vivo falhar ou para responder a perguntas.');
  });

  const total = tempos.reduce((a, b) => a + b, 0);
  console.log('diapositivos:', nSlide, 'tempo planeado (s):', total);
  await pres.writeFile({ fileName: 'Apresentacao_Defesa_UAN.pptx' });
  await applyTheme('Apresentacao_Defesa_UAN.pptx', THEME);
  console.log('ok');
})();
