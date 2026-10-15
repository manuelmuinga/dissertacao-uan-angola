"""Utilizadores e sessões da aplicação web.

- Palavras-passe guardadas com PBKDF2-SHA-256 (sal aleatório, 240 000 iterações),
  só com a biblioteca padrão do Python.
- Sessões do lado do servidor: o navegador guarda só um token aleatório; a base
  de dados guarda o hash desse token, nunca o token.
- Cinco tentativas falhadas bloqueiam a conta durante 5 minutos.
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


def mudar_senha(bd: BaseDados, utilizador: str, senha: str, quem: str) -> None:
    validar_senha(senha)
    with bd.ligacao() as c:
        c.execute("UPDATE utilizadores SET hash_senha = ?, falhas = 0, bloqueado_ate = NULL WHERE utilizador = ?",
                  (hash_senha(senha), utilizador))
        c.execute("DELETE FROM sessoes WHERE utilizador = ?", (utilizador,))
    bd.auditar(quem, "senha_alterada", {"utilizador": utilizador})


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
        """SELECT s.csrf, s.expira_em, u.utilizador, u.nome, u.papel, u.activo
           FROM sessoes s JOIN utilizadores u ON u.utilizador = s.utilizador WHERE s.token_hash = ?""",
        (_h(token),))
    if not r:
        return None
    s = dict(r[0])
    if not s["activo"] or datetime.fromisoformat(s["expira_em"]) < datetime.now(timezone.utc):
        terminar_sessao(bd, token)
        return None
    return s


def terminar_sessao(bd: BaseDados, token: str | None) -> None:
    if token:
        with bd.ligacao() as c:
            c.execute("DELETE FROM sessoes WHERE token_hash = ?", (_h(token),))
