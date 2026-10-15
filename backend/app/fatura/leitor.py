# Leitura da fatura Bradesco
#
# Extrai os lançamentos (despesas) do PDF da fatura Bradesco e
# devolve uma lista estruturada. Pagamentos/créditos são ignorados.
#
# Ainda não trata parcelas nem transações internacionais.

import re
import sys

import pdfplumber

# Linha de lançamento começa com a data "DD/MM "
RE_LINHA_LANCAMENTO = re.compile(r"\d{2}/\d{2} ")
# Valor no fim da linha, ex: "1.940,44" ou "1.940,44-" (pagamento/crédito)
RE_VALOR = re.compile(r"(\d[\d.]*,\d{2})(-?)\s*$")


def _converter_valor(texto: str) -> float:
    """Converte "1.940,44" em 1940.44."""
    return float(texto.replace(".", "").replace(",", "."))


def extrair_lancamentos(pdf_path: str) -> list[dict]:
    """
    Lê a fatura Bradesco e retorna a lista de despesas, cada uma como
    {"data": "DD/MM", "descricao": str, "valor": float}.
    """
    with pdfplumber.open(pdf_path) as pdf:
        texto_completo = ""
        for page in pdf.pages:
            # Os lançamentos ficam na coluna esquerda da página
            coluna_esquerda = page.crop((0, 0, 358, page.height))
            texto_completo += (coluna_esquerda.extract_text() or "") + "\n"

    lancamentos = []
    for linha in texto_completo.split("\n"):
        if not RE_LINHA_LANCAMENTO.match(linha):
            continue
        achado = RE_VALOR.search(linha)
        if achado is None:
            continue  # linha com data mas sem valor no fim (ex: descrição quebrada)
        if achado.group(2) == "-":
            continue  # é pagamento/crédito, não entra na lista
        lancamentos.append({
            "data": linha[:5],
            "descricao": linha[6:achado.start()].strip(),
            "valor": _converter_valor(achado.group(1)),
        })
    return lancamentos


# Só roda quando executado direto: python leitor.py <caminho.pdf>
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python leitor.py <caminho.pdf>")
        sys.exit(1)

    lancamentos = extrair_lancamentos(sys.argv[1])

    print(f"Lançamentos extraídos: {len(lancamentos)}")
    for item in lancamentos[:5]:
        print(f"{item['data']} | {item['descricao']} | R$ {item['valor']:.2f}")
    total = sum(item["valor"] for item in lancamentos)
    print(f"Total: R$ {total:.2f}")
