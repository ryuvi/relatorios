import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from jinja2 import Environment, FileSystemLoader
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import mplcyberpunk
import pathlib
import requests
from bs4 import BeautifulSoup
import schedule
import time


# Função para gerar gráficos
def generate_graphs():
    graph_path = pathlib.Path("graphs")
    graph_path.mkdir(exist_ok=True)

    tickers = ["^BVSP", "^GSPC", "BRL=X"]
    dados_mercado = yf.download(tickers, period="6mo")
    dados_mercado = dados_mercado["Adj Close"]
    dados_mercado = dados_mercado.dropna()
    dados_mercado.columns = ["DOLAR", "IBOVESPA", "S&P500"]

    plt.style.use("cyberpunk")
    plt.plot(dados_mercado["IBOVESPA"])
    plt.title("IBOVESPA")
    plt.savefig(graph_path.joinpath("ibovespa.png"))
    plt.clf()

    plt.plot(dados_mercado["DOLAR"])
    plt.title("DOLAR")
    plt.savefig(graph_path.joinpath("dolar.png"))
    plt.clf()

    plt.plot(dados_mercado["S&P500"])
    plt.title("S&P500")
    plt.savefig(graph_path.joinpath("sp500.png"))
    plt.clf()

    retornos_diarios = dados_mercado.pct_change()
    retorno_dolar = str(round(retornos_diarios["DOLAR"].iloc[-1] * 100, 2)) + "%"
    retorno_ibovespa = str(round(retornos_diarios["IBOVESPA"].iloc[-1] * 100, 2)) + "%"
    retorno_sp = str(round(retornos_diarios["S&P500"].iloc[-1] * 100, 2)) + "%"

    return retorno_dolar, retorno_ibovespa, retorno_sp


# Função para pegar notícias
def get_news():
    url = "https://finance.yahoo.com/news/rssindex"
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "lxml-xml")
    all_news = [news for news in soup.find_all("item")[:5]]
    formated_news = []
    for news in all_news:
        formated_news.append(
            {
                "title": news.find("title").text,
                "link": news.find("link").text,
                "image": news.find("media:content")["url"],
            }
        )
    return formated_news


# Função para criar e enviar e-mail
def send_email(subject, html_content, image_paths, image_cids, recipients):
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["To"] = ", ".join(recipients)
    msg["From"] = "vicenters10@gmail.com"
    msg.attach(MIMEText(html_content, "html"))

    # Adiciona as imagens como anexos e define CIDs
    for image_path, cid in zip(image_paths, image_cids):
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
        image = MIMEImage(img_data)
        image.add_header("Content-ID", f"<{cid}>")
        msg.attach(image)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smpt_server:
        smpt_server.login("vicenters10@gmail.com", "ulog tjxg wkub qfxm")
        smpt_server.sendmail("vicenters10@gmail.com", recipients, msg.as_string())


def process():
    # Geração do gráfico e coleta de notícias
    retorno_dolar, retorno_ibovespa, retorno_sp = generate_graphs()
    formated_news = get_news()

    # Dados para o template
    dados = {
        "data": "12/09/2024",
        "infos": [
            {
                "ativo": "S&P500",
                "descricao": f"O retorno do S&P500 foi",
                "retorno": retorno_sp,
                "color": "green" if float(retorno_sp.replace("%", "")) > 0 else "red",
                "cid_grafico": "sp500.png",
            },
            {
                "ativo": "Dolar",
                "descricao": f"O retorno do Dolar foi",
                "retorno": retorno_dolar,
                "color": (
                    "green" if float(retorno_dolar.replace("%", "")) > 0 else "red"
                ),
                "cid_grafico": "dolar.png",
            },
            {
                "ativo": "Ibovespa",
                "descricao": f"O retorno do Ibovespa foi",
                "retorno": retorno_ibovespa,
                "color": (
                    "green" if float(retorno_ibovespa.replace("%", "")) > 0 else "red"
                ),
                "cid_grafico": "ibovespa.png",
            },
        ],
        "news": formated_news,
        "autor": "Ryuvi",
        "url_cancelamento": "URL_CANCELAMENTO",
        "url_relatorio": "URL_RELATORIO",
    }

    # Renderiza o template
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("index.html")
    html_content = template.render(dados)

    # Define o assunto e os destinatários
    subject = f'Relatório da bolsa do dia {dados["data"]}'
    recipients = ["vicenters10@gmail.com"]

    # Envia o e-mail
    image_paths = ["graphs/sp500.png", "graphs/dolar.png", "graphs/ibovespa.png"]
    image_cids = ["sp500.png", "dolar.png", "ibovespa.png"]

    send_email(subject, html_content, image_paths, image_cids, recipients)


def main():
    # Agendar a execução do processo todo dia às 12h
    schedule.every().day.at("12:00").do(process)

    # Manter o script rodando para verificar o agendamento a cada minuto
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    process()
