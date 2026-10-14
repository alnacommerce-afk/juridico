"""Utilidades comuns: caminhos, JSON, HTTP, fuso horario e data local."""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "juridico-alna/0.1 (monitoramento proprio; contato do titular)"


def data_dir() -> Path:
    """Diretorio PRIVADO (fora do Git). Pode ser sobrescrito por JURIDICO_DATA_DIR."""
    d = Path(os.environ.get("JURIDICO_DATA_DIR", ROOT / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def agora() -> datetime:
    """Hora de Sao Paulo. Brasil nao tem horario de verao desde 2019 (UTC-3);
    usa zoneinfo quando houver tzdata, senao offset fixo."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=-3)))


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


class FonteIndisponivel(Exception):
    """Fonte nao consultada (rede, 5xx, nao configurada)."""


class FalhaAutenticacao(FonteIndisponivel):
    """401/403: exige chave/login/validacao humana. Nao tentar contornar."""


def http_json(url, method="GET", body=None, headers=None, timeout=30, retries=2):
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    h.update(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        h["Content-Type"] = "application/json"
    last = None
    for tentativa in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise FalhaAutenticacao(f"HTTP {e.code} em {url.split('?')[0]}") from e
            last = e
            if e.code < 500 and e.code != 429:
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            last = e
        time.sleep(1.5 * (tentativa + 1))
    raise FonteIndisponivel(f"{type(last).__name__}: {last} ({url.split('?')[0]})")
