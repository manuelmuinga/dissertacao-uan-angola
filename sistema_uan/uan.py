"""Linha de comandos do sistema.

Exemplos (Windows, cmd):
    python uan.py importar dados\\comentarios.csv --plataforma YouTube --via api_oficial --descricao "lote 12"
    python uan.py classificar
    python uan.py fila --n 20
    python uan.py metricas
    python uan.py exportar dados\\revisoes_para_treino.csv
    python uan.py limpar --dias 180
    python uan.py medir-latencia dados\\comentarios.csv --repeticoes 3
    python uan.py criar-utilizador supervisor --nome "Manuel Muinga" --papel supervisor
    python uan.py repor-senha supervisor        (esqueceu a palavra-passe)
    python uan.py servir
    python uan.py copia
    python uan.py fonte-adicionar --tipo rss --endereco https://exemplo.ao/feed --nome "Jornal X"
    python uan.py fontes
    python uan.py recolher
    python uan.py alertas
    python uan.py relatorio --dias 30 --csv dados\\relatorio.csv
    python uan.py relatorio --de 2026-10-01 --ate 2026-10-31 --email
"""

from __future__ import annotations

import argparse
import os
import getpass
import json
import logging
import statistics
import tempfile
import time
from pathlib import Path

from sistema.base_dados import BaseDados
from sistema.classificador import carregar_classificador
from sistema.config import PAPEIS, RAIZ, ROTULOS, obter_config
from sistema.servico import VIAS, classificar_pendentes, exportar_revisoes, importar, metricas


def _clf(cfg):
    return carregar_classificador(cfg.caminho_modelo, max_length=cfg.max_length,
                                  tamanho_lote=cfg.tamanho_lote, dispositivo=cfg.dispositivo)


def _apagar_base(caminho: Path) -> bool:
    """Recria a base de demonstração do zero.

    Tenta apagar o ficheiro; se o Windows não deixar (ficheiro aberto por outro processo), esvazia
    todas as tabelas por dentro, o que tem o mesmo efeito: a demonstração volta a ser criada.
    """
    import gc
    import sqlite3
    import time
    gc.collect()
    for tentativa in range(3):
        try:
            for sufixo in ("", "-wal", "-shm"):
                Path(str(caminho) + sufixo).unlink(missing_ok=True)
            return True
        except PermissionError:
            time.sleep(0.5 * (tentativa + 1))
    c = None
    try:
        c = sqlite3.connect(caminho, timeout=30)
        c.execute("PRAGMA foreign_keys = OFF")
        tabelas = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        for t in tabelas:
            c.execute(f'DELETE FROM "{t}"')
        c.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        if c is not None:
            c.close()


def verificar_config(cfg) -> None:
    from sistema.config import DO_FICHEIRO, ficheiro_env
    f = ficheiro_env()
    print(f"Pasta do sistema: {RAIZ}")
    if f.exists():
        print(f"Ficheiro de configuração: {f}" + ("   (tem .txt no fim; funciona, mas pode renomeá-lo para uan.env)"
                                                   if f.suffix == ".txt" else ""))
    else:
        outros = sorted(p.name for p in RAIZ.glob("uan*env*"))
        print(f"Ficheiro de configuração: NÃO EXISTE ({f})")
        print(f"  Ficheiros parecidos nesta pasta: {', '.join(outros) or 'nenhum'}")

    def estado(nome, valor, obrigatorio=False):
        origem = "uan.env" if nome in DO_FICHEIRO else "cmd (set)"
        if valor:
            print(f"  [ok]  {nome:<20} definido ({len(valor)} caracteres, vem de {origem})")
        else:
            print(f"  [{'!!' if obrigatorio else '--'}]  {nome:<20} vazio" + ("  <- necessário para recolher" if obrigatorio else ""))
    estado("UAN_SEGREDO_HASH", cfg.segredo_hash, True)
    estado("UAN_YOUTUBE_CHAVE", cfg.chave_youtube)
    estado("UAN_CHAVE_API", cfg.chave_api)
    if cfg.caminho_modelo:
        existe = Path(cfg.caminho_modelo).is_dir()
        print(f"  [{'ok' if existe else '!!'}]  UAN_MODELO           {cfg.caminho_modelo}"
              + ("" if existe else "  <- a pasta não existe: deixe UAN_MODELO= vazio ou copie o modelo para lá"))
    else:
        print("  [--]  UAN_MODELO           vazio (classificador de demonstração, por palavras-chave)")
    print(f"  Base de dados: {cfg.caminho_bd}")
    print("Depois de alterar o uan.env, reinicie o servidor (Ctrl+C e python uan.py servir).")


def servir(a, cfg) -> None:
    """Arranca o servidor web num ciclo: a troca de modo pedida na aplicação reinicia-o com a outra base de dados."""
    import uvicorn
    from sistema import controlo
    from sistema.demonstracao import CONTAS, SENHA, caminho_bd, precisa_recriar
    bd_real = Path(cfg.caminho_bd)
    bd_demo = caminho_bd(bd_real.parent)
    from sistema.config import DO_FICHEIRO, recarregar_env
    # só o que veio do cmd; o que vem do uan.env é lido de novo em cada arranque
    originais = {k: (None if k in DO_FICHEIRO else os.environ.get(k))
                 for k in ("UAN_BD", "UAN_DEMONSTRACAO", "UAN_MODELO", "UAN_SEGREDO_HASH")}
    endereco = f"http://{'127.0.0.1' if a.anfitriao == '0.0.0.0' else a.anfitriao}:{a.porta}"
    modo, repor = ("demonstracao" if a.demonstracao else "real"), a.repor
    try:
        while True:
            for k, v in originais.items():  # cada arranque parte da configuração original
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            recarregar_env()  # alterações ao uan.env contam a partir deste arranque (também ao mudar de modo)
            if modo == "demonstracao":
                if not repor and precisa_recriar(bd_demo):
                    print("Os dados fictícios foram melhorados nesta versão: a base de demonstração vai ser recriada.")
                    repor = True
                if repor and not _apagar_base(bd_demo):
                    print("\nNão foi possível recriar a base de demonstração: o ficheiro está aberto noutro programa.\n"
                          "Feche outras janelas onde o sistema esteja a correr (ou programas que tenham aberto\n"
                          f"{bd_demo}) e arranque de novo. Por agora continua com os dados fictícios anteriores.\n")
                os.environ.update(UAN_DEMONSTRACAO="1", UAN_BD=str(bd_demo))
                os.environ.pop("UAN_MODELO", None)
                os.environ.setdefault("UAN_SEGREDO_HASH", "demonstracao")
                print(f"MODO DE DEMONSTRAÇÃO: dados fictícios em {bd_demo}. A base de dados real não é usada.")
                print(f"Contas: {', '.join(u for u, _, _ in CONTAS)} (palavra-passe: {SENHA})")
            else:
                os.environ["UAN_DEMONSTRACAO"] = "0"
                print(f"MODO REAL: base de dados {bd_real}.")
            repor = False
            os.environ["UAN_ENDERECO_SERVIDOR"] = endereco
            print("A preparar o sistema" + (" e os dados fictícios" if modo == "demonstracao" else "") +
                  "... aguarde pela mensagem PRONTO antes de abrir o navegador.", flush=True)
            servidor = uvicorn.Server(uvicorn.Config("sistema.web.app:criar_app", factory=True, host=a.anfitriao,
                                                     port=a.porta, log_level="warning"))
            controlo.servidor, controlo.pedido = servidor, None
            servidor.run()
            if not controlo.pedido:
                break
            modo = controlo.pedido
            print(f"\nA mudar para o modo {'de demonstração' if modo == 'demonstracao' else 'real'}...\n", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        controlo.servidor = None
    print("Sistema parado.")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="uan")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("importar"); p.add_argument("ficheiro"); p.add_argument("--plataforma", required=True)
    p.add_argument("--via", required=True, choices=VIAS); p.add_argument("--descricao")
    sub.add_parser("classificar")
    p = sub.add_parser("fila"); p.add_argument("--n", type=int, default=20); p.add_argument("--categoria", choices=ROTULOS)
    sub.add_parser("metricas")
    p = sub.add_parser("exportar"); p.add_argument("destino")
    p = sub.add_parser("limpar"); p.add_argument("--dias", type=int)
    p = sub.add_parser("medir-latencia", help="Mede importação+classificação numa BD temporária (H2)")
    p.add_argument("ficheiro"); p.add_argument("--repeticoes", type=int, default=3); p.add_argument("--plataforma", default="teste")
    p = sub.add_parser("servir", help="Arranca a aplicação web")
    p.add_argument("--porta", type=int, default=8000)
    p.add_argument("--anfitriao", default="127.0.0.1",
                   help="127.0.0.1 = só este computador; 0.0.0.0 = toda a rede local (use com cuidado)")
    p.add_argument("--demonstracao", action="store_true",
                   help="arranca com uma base de dados SEPARADA e dados fictícios (para apresentações)")
    p.add_argument("--repor", action="store_true", help="com --demonstracao: apaga e recria os dados fictícios")
    p = sub.add_parser("criar-utilizador", help="Cria uma conta (pede a palavra-passe)")
    p.add_argument("utilizador"); p.add_argument("--nome", required=True); p.add_argument("--papel", choices=PAPEIS, default="analista")
    p = sub.add_parser("repor-senha", help="Repõe a palavra-passe de uma conta e desbloqueia-a (quando o supervisor a esqueceu)")
    p.add_argument("utilizador")
    p.add_argument("--temporaria", action="store_true", help="gera uma palavra-passe temporária, a mudar ao entrar")
    p.add_argument("--demonstracao", action="store_true", help="na base de demonstração (dados\\demonstracao.db)")
    sub.add_parser("verificar-config", help="Mostra que ficheiro uan.env é lido e que valores estão definidos (sem os mostrar)")
    sub.add_parser("copia", help="Cópia de segurança da base de dados para dados\\copias")
    from sistema.recolha import TIPOS as TIPOS_FONTE
    p = sub.add_parser("fonte-adicionar", help="Acrescenta uma ou mais fontes de recolha (tipo detectado automaticamente)")
    p.add_argument("--tipo", default="auto", choices=["auto"] + list(TIPOS_FONTE))
    p.add_argument("--endereco", required=True, nargs="+", help="um ou mais endereços, identificadores ou termos (entre aspas)")
    p.add_argument("--nome", default=""); p.add_argument("--max", type=int, default=100)
    sub.add_parser("fontes", help="Lista as fontes de recolha")
    p = sub.add_parser("recolher", help="Recolhe das fontes activas (ou de uma) e classifica o que for novo")
    p.add_argument("--fonte", type=int); p.add_argument("--sem-classificar", action="store_true")
    sub.add_parser("alertas", help="Verifica tendências, envia os alertas por e-mail e lista os mais recentes")
    p = sub.add_parser("relatorio", help="Relatório de alertas de ameaças para um período")
    p.add_argument("--de"); p.add_argument("--ate"); p.add_argument("--dias", default="30")
    p.add_argument("--csv", help="grava o relatório em CSV neste ficheiro")
    p.add_argument("--email", action="store_true", help="envia o resumo aos destinatários definidos")
    a = ap.parse_args(argv)

    cfg = obter_config()
    if a.cmd == "verificar-config":
        verificar_config(cfg)
        return
    if a.cmd == "servir":
        servir(a, cfg)
        return
    bd = BaseDados(cfg.caminho_bd)
    if a.cmd == "criar-utilizador":
        from sistema.utilizadores import criar_utilizador
        senha = getpass.getpass("Palavra-passe (mín. 10 caracteres): ")
        if senha != getpass.getpass("Repetir: "):
            raise SystemExit("As palavras-passe não coincidem.")
        criar_utilizador(bd, a.utilizador, a.nome, a.papel, senha, quem="linha_de_comandos")
        print(f"Utilizador {a.utilizador} ({a.papel}) criado.")
        return
    if a.cmd == "repor-senha":
        from sistema.utilizadores import mudar_senha, repor_temporaria
        if a.demonstracao:
            from sistema.demonstracao import caminho_bd
            bd = BaseDados(caminho_bd(Path(cfg.caminho_bd).parent))
        u = a.utilizador.strip().lower()
        if not bd.consultar("SELECT 1 FROM utilizadores WHERE utilizador = ?", (u,)):
            contas = ", ".join(r["utilizador"] for r in bd.consultar("SELECT utilizador FROM utilizadores ORDER BY 1"))
            raise SystemExit(f"O utilizador {u} não existe. Contas nesta base de dados: {contas or 'nenhuma'}.")
        with bd.ligacao() as c:  # quem repõe na linha de comandos também reactiva a conta
            c.execute("UPDATE utilizadores SET activo = 1 WHERE utilizador = ?", (u,))
        if a.temporaria:
            senha = repor_temporaria(bd, u, quem="linha_de_comandos")
            print(f"Palavra-passe temporária de {u}: {senha}")
            print("Tem de ser mudada logo ao entrar.")
        else:
            senha = getpass.getpass("Nova palavra-passe (mín. 10 caracteres): ")
            if senha != getpass.getpass("Repetir: "):
                raise SystemExit("As palavras-passe não coincidem.")
            mudar_senha(bd, u, senha, quem="linha_de_comandos")
            print(f"Palavra-passe de {u} alterada. A conta foi desbloqueada.")
        return
    if a.cmd == "copia":
        from datetime import datetime
        destino = Path(cfg.caminho_bd).parent / "copias" / datetime.now().strftime("sistema_%Y%m%d_%H%M%S.db")
        print(f"Cópia criada: {bd.copia_seguranca(destino, quem='linha_de_comandos')}")
        return
    if a.cmd == "fonte-adicionar":
        from sistema.recolha import TIPOS as TF, adicionar_fontes
        r = adicionar_fontes(bd, "\n".join(a.endereco), "linha_de_comandos", a.tipo, a.nome, a.max)
        for idf, t, e in r["criadas"]:
            print(f"Fonte {idf} acrescentada: {TF[t]} · {e}")
        for e in r["repetidas"]:
            print(f"Já existia: {e}")
        for e, m in r["erros"]:
            print(f"Erro em {e}: {m}")
        return
    if a.cmd == "fontes":
        for f in bd.consultar("SELECT * FROM fontes ORDER BY id_fonte"):
            print(f"{f['id_fonte']:>3} {'activa  ' if f['activa'] else 'inactiva'} {f['tipo']:<14} {f['nome'][:30]:<30} "
                  f"{(f['ultimo_estado'] or '')[:60]}")
        return
    if a.cmd == "recolher":
        from sistema.recolha import recolher_fonte, recolher_todas
        res = [recolher_fonte(bd, cfg, a.fonte, "linha_de_comandos")] if a.fonte else recolher_todas(bd, cfg, "linha_de_comandos")
        for r in res:
            print(f"[{r['id_fonte']}] {r['nome']}: {r['estado']}")
        if not a.sem_classificar and any(r.get("novos") for r in res):
            print(json.dumps(classificar_pendentes(bd, _clf(cfg), limite=10**9), ensure_ascii=False))
        return
    if a.cmd == "alertas":
        from sistema import alertas as al
        novos = al.verificar_tendencias(bd)
        al.notificar(bd, cfg, novos, sincrono=True)
        print(f"{len(novos)} alerta(s) de tendência novo(s).")
        for r in bd.consultar("SELECT * FROM alertas ORDER BY id_alerta DESC LIMIT 15"):
            print(f"{r['id_alerta']:>4} {r['criado_em'][:16]} {r['tipo']:<10} {r['titulo'][:90]}  [e-mail: {r['email_estado']}]")
        return
    if a.cmd == "relatorio":
        from sistema import alertas as al
        rel = al.relatorio(bd, al.periodo(a.de, a.ate, a.dias))
        k = rel["kpi"]
        print(f"{rel['periodo'].rotulo()}: {k['publicacoes']} publicações, {k['sinalizadas']} sinalizadas, "
              f"{k['confirmadas']} ameaças confirmadas, {k['alertas']} alertas")
        if a.csv:
            Path(a.csv).write_text("\ufeff" + al.relatorio_csv(rel), encoding="utf-8")
            print(f"CSV gravado em {a.csv}")
        if a.email:
            assunto, corpo = al.corpo_relatorio(rel, cfg)
            al.enviar_email(cfg, al.ler_definicoes(bd)["destinatarios"], assunto, corpo)
            print("Resumo enviado por e-mail.")
        bd.auditar("linha_de_comandos", "relatorio", {"periodo": rel["periodo"].rotulo()})
        return
    if a.cmd == "importar":
        print(json.dumps(importar(bd, Path(a.ficheiro), a.plataforma, a.via, cfg.segredo_hash, a.descricao,
                                 quem="linha_de_comandos"), ensure_ascii=False))
    elif a.cmd == "classificar":
        print(json.dumps(classificar_pendentes(bd, _clf(cfg), limite=10**9), ensure_ascii=False))
    elif a.cmd == "fila":
        for i, r in enumerate(bd.fila(a.n, a.categoria), 1):
            print(f"{i:>3}. [{r['categoria']:<13} {r['confianca']:.2f} | prior. {r['prioridade']:.2f}] {r['texto'][:110]}")
    elif a.cmd == "metricas":
        print(json.dumps(metricas(bd), ensure_ascii=False, indent=1))
    elif a.cmd == "exportar":
        print(f"{exportar_revisoes(bd, Path(a.destino))} revisões exportadas para {a.destino}")
    elif a.cmd == "limpar":
        print(f"{bd.apagar_antigos(a.dias or cfg.dias_conservacao)} publicações apagadas")
    elif a.cmd == "medir-latencia":
        clf = _clf(cfg)
        tempos, primeiros, n, passo = [], [], 0, None
        for _ in range(a.repeticoes):
            with tempfile.TemporaryDirectory() as d:
                bdt = BaseDados(Path(d) / "t.db")
                t0 = time.perf_counter()
                info = importar(bdt, Path(a.ficheiro), a.plataforma, "manual", cfg.segredo_hash or "medicao", "medição de latência")
                t_imp = time.perf_counter() - t0
                out = classificar_pendentes(bdt, clf, limite=10**9)
                tempos.append(time.perf_counter() - t0); n = info["novos"]
                primeiros.append(t_imp + out.get("segundos_ate_primeiro_sublote", 0)); passo = out.get("sublote")
        print(json.dumps({"modelo": clf.nome, "itens": n, "repeticoes": a.repeticoes, "sublote": passo,
                          "segundos_total_mediana": round(statistics.median(tempos), 3),
                          "ms_por_item_mediana": round(1000 * statistics.median(tempos) / max(n, 1), 2),
                          "segundos_ate_primeiro_sublote_na_fila_mediana": round(statistics.median(primeiros), 3)},
                         ensure_ascii=False))


if __name__ == "__main__":
    main()
