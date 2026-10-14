"""Saude de portais oficiais via Playwright (opcional). NAO contorna CAPTCHA/login:
detecta a barreira e sinaliza 'requer intervencao humana'."""
import re

BARREIRAS = re.compile(r"captcha|recaptcha|hcaptcha|cloudflare|verifique que voc[eê] [eé] humano|"
                       r"acesso negado|fa[cç]a login|entrar com gov\.br|certificado digital", re.I)


def detectar_barreira(texto: str):
    m = BARREIRAS.search(texto or "")
    return m.group(0) if m else None


def checar_portal(url: str, timeout_ms=30000):
    """Retorna {'status': 'ok'|'requer_humano'|'indisponivel'|'nao_configurada', 'detalhe': str}."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "nao_configurada",
                "detalhe": "Playwright nao instalado (pip install playwright && playwright install chromium)"}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            pg = b.new_page()
            resp = pg.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            pg.wait_for_timeout(3000)  # portais com frames/JS (ex.: Projudi) carregam depois
            texto = ""
            for f in pg.frames:  # inclui iframes: CAPTCHA costuma estar em frame de terceiros
                texto += f" {f.url} "
                try:
                    texto += f.locator("body").inner_text(timeout=4000)[:20000]
                except Exception:
                    pass
            b.close()
        barreira = detectar_barreira(texto)
        if barreira:
            return {"status": "requer_humano", "detalhe": f"barreira detectada: {barreira}"}
        if resp and resp.status >= 400:
            return {"status": "indisponivel", "detalhe": f"HTTP {resp.status}"}
        return {"status": "ok", "detalhe": "pagina carregou (consulta por parte NAO executada)"}
    except Exception as e:  # rede, timeout, navegador ausente
        return {"status": "indisponivel", "detalhe": f"{type(e).__name__}: {e}"[:200]}
