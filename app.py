import openai
import fitz  # PyMuPDF
from flask import Flask, request, render_template, send_file
import io
import re
import os
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

# Prompt completo e otimizado
PROMPT_BASE = """
Você é um assistente jurídico especializado em interpretar e organizar informações de Convenções Coletivas de Trabalho (CCT). Seu objetivo é extrair e apresentar, de forma clara e estruturada, todos os trechos relevantes da convenção para apoiar o setor de Recursos Humanos ou Departamento Pessoal em suas decisões.

Instrução:
Tenho um documento PDF contendo uma Convenção Coletiva de Trabalho (CCT) e preciso que você extraia e organize todas as informações sobre os seguintes temas:

1. Vigência e Abrangência  
Data de início e término da convenção.  
Categorias profissionais abrangidas.  
Região de abrangência.

2. Salários e Reajustes  
Percentual de reajuste e data de aplicação.  
Pisos salariais por função/categoria.  
Formas de pagamento e retroatividade.

3. Pagamento e Benefícios  
Vale-transporte, vale-refeição, cesta básica e convênios médicos.  
Vale-Refeição: além do valor e forma de pagamento, verificar se há outras formas de fornecimento, como restaurante na empresa ou convênios com terceiros. Indicar possíveis exceções que isentam a empresa do pagamento.  
Auxílio saúde e benefícios assistenciais.  
Quebra de Caixa: verificar se há cláusula para trabalhadores que manuseiam numerário e se há adicional correspondente.  
Auxílio Plano Assistência e Cuidados Pessoais: identificar se há valores pagos para assistência médica, odontológica ou psicológica.

4. Jornada de Trabalho e Adicionais  
Carga horária e compensações.  
Pagamento de horas extras e adicional noturno.  
Regras de banco de horas e compensações de feriados.

5. Férias, Rescisão e Estabilidades  
Procedimentos para pagamento e prazos.  
Estabilidade de Férias: verificar se há proibição de dispensa antes ou depois das férias.  
Estabilidades previstas (gestante, pré-aposentadoria, afastados por doença/acidente etc.).  
Multas por atraso e homologação no sindicato.

6. Contribuições Sindicais e Assistenciais  
Valores e regras para descontos.  
Oposição: verificar prazo, métodos permitidos para formalização da oposição e se há necessidade de comparecimento presencial ao sindicato.  
Contribuições patronais e seus valores.  
Prazos de recolhimento e penalidades por atraso.

7. Multas e Penalidades  
Percentual e cálculo de multas por descumprimento.  
Penalidades por não cumprimento de obrigações trabalhistas.

📌 Formato da Resposta:
- Transcreva os trechos completos do documento, sem resumir as cláusulas.
- Indique sempre o número da cláusula e a página onde cada item foi encontrado.
- Estruture a resposta como um e-mail profissional, organizado por seções, pronto para envio ao setor de Recursos Humanos ou Departamento Pessoal.
- Use uma linguagem formal, técnica e objetiva.
- Comece com a saudação:  
  “Prezados,  
  Segue abaixo a análise da Convenção Coletiva conforme os tópicos de interesse do Departamento Pessoal.”
- Finalize com:  
  “Em caso de dúvidas sobre as cláusulas acima, estamos à disposição.”
"""

# Função para limpar texto do PDF
def limpar_texto(texto):
    texto = re.sub(r"\n{2,}", "\n", texto)
    texto = re.sub(r"\s{2,}", " ", texto)
    texto = re.sub(r"Página\s+\d+", "", texto, flags=re.IGNORECASE)
    return texto.strip()

# Função para extrair somente as páginas úteis
def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    texto = ""
    for page in doc:
        conteudo = page.get_text()
        if "cláusula" in conteudo.lower():
            texto += conteudo
    return limpar_texto(texto)

# Função para dividir o texto em blocos maiores
def dividir_texto_em_blocos(texto, max_chars=12000):
    palavras = texto.split()
    blocos = []
    bloco = []
    tamanho_atual = 0
    for palavra in palavras:
        tamanho_atual += len(palavra) + 1
        bloco.append(palavra)
        if tamanho_atual >= max_chars:
            blocos.append(" ".join(bloco))
            bloco = []
            tamanho_atual = 0
    if bloco:
        blocos.append(" ".join(bloco))
    return blocos

@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None
    erro = None

    if request.method == "POST":
        if "pdf_file" not in request.files:
            erro = "Nenhum arquivo foi enviado."
        else:
            pdf_file = request.files["pdf_file"]
            if pdf_file.filename == "":
                erro = "Arquivo inválido."
            else:
                try:
                    texto_extraido = extract_text_from_pdf(pdf_file)
                    blocos = dividir_texto_em_blocos(texto_extraido)

                    respostas = []
                    for bloco in blocos:
                        mensagem = [
                            {"role": "system", "content": "Você é um assistente jurídico que organiza convenções coletivas para o setor de RH."},
                            {"role": "user", "content": PROMPT_BASE + "\n\n" + bloco}
                        ]
                        resposta = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo-0125",
                            messages=mensagem,
                            temperature=0.4
                        )
                        respostas.append(resposta["choices"][0]["message"]["content"])

                    resultado = "\n\n".join(respostas)

                    with open("texto_extraido.txt", "w", encoding="utf-8") as f:
                        f.write(resultado)

                except Exception as e:
                    erro = f"Erro ao processar: {str(e)}"

    return render_template("index.html", resultado=resultado, erro=erro)

@app.route("/download")
def download_text():
    return send_file("texto_extraido.txt", as_attachment=True, download_name="texto_extraido.txt")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)