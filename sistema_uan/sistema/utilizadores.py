"""Utilizadores e sessões da aplicação web.

- Palavras-passe guardadas com PBKDF2-SHA-256 (sal aleatório, 240 000 iterações),
  só com a biblioteca padrão do Python.
- Sessões do lado do servidor: o navegador guarda só um token aleatório; a base
  de dados guarda o hash desse token, nunca o token.
- Cinco tentativas falhadas bloqueiam a conta durante 5 minutos.
- Recuperação de quem esquece a palavra-passe, sem e-mail nem serviços externos:
  * código de recuperação pessoal (gerado em «A minha conta», mostrado uma só vez,
    guardado como hash, serve uma vez);
  * pedido ao supervisor, que gera uma palavra-passe temporária (mudança obrigatória ao entrar);
  * na linha de comandos, «python uan.py repor-senha <utilizador>» (para o último supervisor).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from .base_dados import BaseDados, agora
from .config import PAPEIS

ITERACOES = 240_000
MAX_FALHAS = 5
MINUTOS_BLOQUEIO = 5
SEGUNDOS_FECHO = 20  # depois de a janela fechar, a sessão termina se nenhuma página do sistema abrir neste prazo
_NOME_VALIDO = re.compile(r"^[a-z0-9._-]{3,32}$")


class ErroAutenticacao(Exception):
    pass


def hash_senha(senha: str, sal: bytes | None = None, iteracoes: int = ITERACOES) -> str:
    sal = sal or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, iteracoes)
    return f"pbkdf2_sha256${iteracoes}${sal.hex()}${dk.hex()}"


def verificar_senha(senha: str, guardado: str) -> bool:
    try:
        alg, it, sal, dk = guardado.split("$")
    except ValueError:
        return False
    if alg != "pbkdf2_sha256":
        return False
    calc = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), int(it))
    return hmac.compare_digest(calc.hex(), dk)


def validar_senha(senha: str) -> None:
    if len(senha) < 10:
        raise ValueError("A palavra-passe deve ter pelo menos 10 caracteres.")


def criar_utilizador(bd: BaseDados, utilizador: str, nome: str, papel: str, senha: str, quem: str = "sistema") -> None:
    utilizador = utilizador.strip().lower()
    if not _NOME_VALIDO.match(utilizador):
        raise ValueError("Nome de utilizador: 3 a 32 caracteres, só letras minúsculas, algarismos, ponto, hífen ou _.")
    if papel not in PAPEIS:
        raise ValueError(f"Papel deve ser um de {PAPEIS}.")
    validar_senha(senha)
    if bd.consultar("SELECT 1 FROM utilizadores WHERE utilizador = ?", (utilizador,)):
        raise ValueError(f"O utilizador {utilizador} já existe.")
    with bd.ligacao() as c:
        c.execute("INSERT INTO utilizadores(utilizador, nome, papel, hash_senha, criado_em) VALUES (?,?,?,?,?)",
                  (utilizador, nome.strip() or utilizador, papel, hash_senha(senha), agora()))
    bd.auditar(quem, "utilizador_criado", {"utilizador": utilizador, "papel": papel})


def mudar_senha(bd: BaseDados, utilizador: str, senha: str, quem: str, temporaria: bool = False) -> None:
    """Define a palavra-passe, desbloqueia a conta e termina as sessões abertas.

    temporaria=True: a pessoa tem de a mudar logo que entrar (usada quando outra pessoa a definiu).
    """
    validar_senha(senha)
    if not bd.consultar("SELECT 1 FROM utilizadores WHERE utilizador = ?", (utilizador,)):
        raise ValueError(f"O utilizador {utilizador} não existe.")
    with bd.ligacao() as c:
        c.execute("""UPDATE utilizadores SET hash_senha = ?, falhas = 0, bloqueado_ate = NULL, senha_temporaria = ?
                     WHERE utilizador = ?""", (hash_senha(senha), int(temporaria), utilizador))
        c.execute("DELETE FROM sessoes WHERE utilizador = ?", (utilizador,))
    bd.auditar(quem, "senha_temporaria_definida" if temporaria else "senha_alterada", {"utilizador": utilizador})


# ---------------------------------------------------------------------------- recuperação
_ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O nem 1/I/L, fáceis de confundir ao copiar


def _aleatorio(n: int, grupo: int = 4) -> str:
    x = "".join(secrets.choice(_ALFABETO) for _ in range(n))
    return "-".join(x[i:i + grupo] for i in range(0, n, grupo))


def _normalizar_codigo(codigo: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (codigo or "").upper())


def gerar_codigo_recuperacao(bd: BaseDados, utilizador: str) -> str:
    """Novo código pessoal (16 caracteres, cerca de 80 bits). Substitui o anterior; mostra-se uma só vez."""
    codigo = _aleatorio(16)
    with bd.ligacao() as c:
        c.execute("UPDATE utilizadores SET codigo_recuperacao = ?, codigo_criado_em = ? WHERE utilizador = ?",
                  (hash_senha(_normalizar_codigo(codigo)), agora(), utilizador))
    bd.auditar(utilizador, "codigo_recuperacao_gerado", None)
    return codigo


def _falha(bd: BaseDados, u: dict, motivo: str, accao: str) -> None:
    falhas = u["falhas"] + 1
    bloqueio = (datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_BLOQUEIO)).isoformat() if falhas >= MAX_FALHAS else None
    with bd.ligacao() as c:
        c.execute("UPDATE utilizadores SET falhas = ?, bloqueado_ate = ? WHERE utilizador = ?",
                  (0 if bloqueio else falhas, bloqueio, u["utilizador"]))
    bd.auditar(u["utilizador"], accao, {"motivo": motivo})


def recuperar_com_codigo(bd: BaseDados, utilizador: str, codigo: str, senha: str, senha2: str) -> None:
    """Muda a palavra-passe com o código de recuperação. O código deixa de valer depois de usado.

    Conta para o mesmo limite de tentativas que a entrada (5 falhas bloqueiam 5 minutos).
    """
    utilizador = (utilizador or "").strip().lower()
    erro = "Utilizador ou código de recuperação incorrectos."
    if senha != senha2:
        raise ValueError("As duas palavras-passe novas não coincidem.")
    validar_senha(senha)
    r = bd.consultar("SELECT * FROM utilizadores WHERE utilizador = ?", (utilizador,))
    if not r:
        hash_senha("x")
        bd.auditar(utilizador or "?", "recuperacao_falhada", {"motivo": "desconhecido"})
        raise ErroAutenticacao(erro)
    u = dict(r[0])
    if u["bloqueado_ate"] and datetime.fromisoformat(u["bloqueado_ate"]) > datetime.now(timezone.utc):
        raise ErroAutenticacao("Conta bloqueada temporariamente por tentativas falhadas. Tente daqui a alguns minutos.")
    if not u["activo"] or not u["codigo_recuperacao"] or \
            not verificar_senha(_normalizar_codigo(codigo), u["codigo_recuperacao"]):
        motivo = "inactivo" if not u["activo"] else ("sem_codigo" if not u["codigo_recuperacao"] else "codigo")
        _falha(bd, u, motivo, "recuperacao_falhada")
        raise ErroAutenticacao(erro)
    mudar_senha(bd, utilizador, senha, quem=utilizador)
    with bd.ligacao() as c:
        c.execute("UPDATE utilizadores SET codigo_recuperacao = NULL, codigo_criado_em = NULL WHERE utilizador = ?",
                  (utilizador,))
        c.execute("""UPDATE pedidos_recuperacao SET estado = 'resolvido', resolvido_por = ?, resolvido_em = ?
                     WHERE utilizador = ? AND estado = 'pendente'""", (utilizador, agora(), utilizador))
    bd.auditar(utilizador, "senha_recuperada_com_codigo", None)


def pedir_recuperacao(bd: BaseDados, utilizador: str) -> None:
    """Regista um pedido para os supervisores. Responde sempre da mesma forma (não revela se a conta existe)."""
    utilizador = (utilizador or "").strip().lower()
    r = bd.consultar("SELECT activo FROM utilizadores WHERE utilizador = ?", (utilizador,))
    if not r or not r[0]["activo"]:
        bd.auditar(utilizador[:40] or "?", "recuperacao_pedida", {"motivo": "desconhecido" if not r else "inactivo"})
        return
    if bd.consultar("SELECT 1 FROM pedidos_recuperacao WHERE utilizador = ? AND estado = 'pendente'", (utilizador,)):
        return  # já há um pedido à espera
    with bd.ligacao() as c:
        c.execute("INSERT INTO pedidos_recuperacao(utilizador, pedido_em) VALUES (?, ?)", (utilizador, agora()))
    bd.auditar(utilizador, "recuperacao_pedida", None)


def pedidos_pendentes(bd: BaseDados) -> list[dict]:
    return [dict(r) for r in bd.consultar(
        """SELECT p.id_pedido, p.utilizador, p.pedido_em, u.nome, u.papel FROM pedidos_recuperacao p
           JOIN utilizadores u ON u.utilizador = p.utilizador WHERE p.estado = 'pendente' ORDER BY p.pedido_em""")]


def repor_temporaria(bd: BaseDados, utilizador: str, quem: str) -> str:
    """Gera uma palavra-passe temporária (mudança obrigatória ao entrar) e fecha os pedidos pendentes."""
    if utilizador == quem:
        raise ValueError("Para a sua própria conta use «A minha conta».")
    senha = _aleatorio(12).lower()
    mudar_senha(bd, utilizador, senha, quem, temporaria=True)
    with bd.ligacao() as c:
        c.execute("""UPDATE pedidos_recuperacao SET estado = 'resolvido', resolvido_por = ?, resolvido_em = ?
                     WHERE utilizador = ? AND estado = 'pendente'""", (quem, agora(), utilizador))
    return senha


def recusar_pedido(bd: BaseDados, id_pedido: int, quem: str) -> None:
    with bd.ligacao() as c:
        c.execute("""UPDATE pedidos_recuperacao SET estado = 'recusado', resolvido_por = ?, resolvido_em = ?
                     WHERE id_pedido = ? AND estado = 'pendente'""", (quem, agora(), id_pedido))
    bd.auditar(quem, "recuperacao_recusada", {"pedido": id_pedido})


def definir_activo(bd: BaseDados, utilizador: str, activo: bool, quem: str) -> None:
    if not activo and utilizador == quem:
        raise ValueError("Não pode desactivar a sua própria conta.")
    if not activo:
        sup = bd.consultar("SELECT COUNT(*) AS n FROM utilizadores WHERE papel='supervisor' AND activo=1 AND utilizador != ?",
                           (utilizador,))[0]["n"]
        papel = bd.consultar("SELECT papel FROM utilizadores WHERE utilizador = ?", (utilizador,))
        if papel and papel[0]["papel"] == "supervisor" and sup == 0:
            raise ValueError("Tem de ficar pelo menos um supervisor activo.")
    with bd.ligacao() as c:
        c.execute("UPDATE utilizadores SET activo = ? WHERE utilizador = ?", (int(activo), utilizador))
        if not activo:
            c.execute("DELETE FROM sessoes WHERE utilizador = ?", (utilizador,))
    bd.auditar(quem, "utilizador_activado" if activo else "utilizador_desactivado", {"utilizador": utilizador})


def autenticar(bd: BaseDados, utilizador: str, senha: str) -> dict:
    utilizador = (utilizador or "").strip().lower()
    r = bd.consultar("SELECT * FROM utilizadores WHERE utilizador = ?", (utilizador,))
    if not r:
        hash_senha(senha or "x")  # mesmo custo de tempo para utilizadores inexistentes
        bd.auditar(utilizador or "?", "entrada_falhada", {"motivo": "desconhecido"})
        raise ErroAutenticacao("Utilizador ou palavra-passe incorrectos.")
    u = dict(r[0])
    agora_dt = datetime.now(timezone.utc)
    if u["bloqueado_ate"] and datetime.fromisoformat(u["bloqueado_ate"]) > agora_dt:
        raise ErroAutenticacao("Conta bloqueada temporariamente por tentativas falhadas. Tente daqui a alguns minutos.")
    if not u["activo"] or not verificar_senha(senha or "", u["hash_senha"]):
        falhas = u["falhas"] + 1
        bloqueio = (agora_dt + timedelta(minutes=MINUTOS_BLOQUEIO)).isoformat() if falhas >= MAX_FALHAS else None
        with bd.ligacao() as c:
            c.execute("UPDATE utilizadores SET falhas = ?, bloqueado_ate = ? WHERE utilizador = ?",
                      (0 if bloqueio else falhas, bloqueio, utilizador))
        bd.auditar(utilizador, "entrada_falhada", {"motivo": "inactivo" if not u["activo"] else "senha"})
        raise ErroAutenticacao("Utilizador ou palavra-passe incorrectos.")
    with bd.ligacao() as c:
        c.execute("UPDATE utilizadores SET falhas = 0, bloqueado_ate = NULL, ultimo_acesso = ? WHERE utilizador = ?",
                  (agora(), utilizador))
    return {k: u[k] for k in ("utilizador", "nome", "papel")}


def _h(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_sessao(bd: BaseDados, utilizador: str, horas: int) -> str:
    token = secrets.token_urlsafe(32)
    expira = (datetime.now(timezone.utc) + timedelta(hours=horas)).isoformat()
    with bd.ligacao() as c:
        c.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora(),))
        c.execute("INSERT INTO sessoes(token_hash, utilizador, csrf, criada_em, expira_em) VALUES (?,?,?,?,?)",
                  (_h(token), utilizador, secrets.token_urlsafe(24), agora(), expira))
    bd.auditar(utilizador, "entrada", None)
    return token


def obter_sessao(bd: BaseDados, token: str | None) -> dict | None:
    if not token:
        return None
    r = bd.consultar(
        """SELECT s.csrf, s.expira_em, s.fecho_em, u.utilizador, u.nome, u.papel, u.activo, u.senha_temporaria,
                  u.codigo_criado_em
           FROM sessoes s JOIN utilizadores u ON u.utilizador = s.utilizador WHERE s.token_hash = ?""",
        (_h(token),))
    if not r:
        return None
    s = dict(r[0])
    agora_dt = datetime.now(timezone.utc)
    if not s["activo"] or datetime.fromisoformat(s["expira_em"]) < agora_dt:
        terminar_sessao(bd, token)
        return None
    if s["fecho_em"]:
        if (agora_dt - datetime.fromisoformat(s["fecho_em"])).total_seconds() > SEGUNDOS_FECHO:
            terminar_sessao(bd, token)
            bd.auditar(s["utilizador"], "saida", {"motivo": "janela_fechada"})
            return None
        marcar_fecho(bd, token, False)  # voltou a abrir (recarregou ou mudou de página): continua
        s["fecho_em"] = None
    return s


def marcar_fecho(bd: BaseDados, token: str | None, fechou: bool = True) -> None:
    """A janela do navegador foi fechada (fechou=True) ou voltou a abrir (False)."""
    if token:
        with bd.ligacao() as c:
            c.execute("UPDATE sessoes SET fecho_em = ? WHERE token_hash = ?", (agora() if fechou else None, _h(token)))


def limpar_sessoes_fechadas(bd: BaseDados) -> int:
    """Termina as sessões cuja janela fechou há mais de SEGUNDOS_FECHO segundos."""
    limite = (datetime.now(timezone.utc) - timedelta(seconds=SEGUNDOS_FECHO)).isoformat()
    linhas = bd.consultar("SELECT token_hash, utilizador FROM sessoes WHERE fecho_em IS NOT NULL AND fecho_em < ?",
                          (limite,))
    with bd.ligacao() as c:
        for l in linhas:
            c.execute("DELETE FROM sessoes WHERE token_hash = ?", (l["token_hash"],))
    for l in linhas:
        bd.auditar(l["utilizador"], "saida", {"motivo": "janela_fechada"})
    return len(linhas)


def terminar_sessao(bd: BaseDados, token: str | None) -> None:
    if token:
        with bd.ligacao() as c:
            c.execute("DELETE FROM sessoes WHERE token_hash = ?", (_h(token),))
