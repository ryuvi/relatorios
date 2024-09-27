import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from jinja2 import Environment, FileSystemLoader
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import pathlib
import requests
from bs4 import BeautifulSoup
import mplcyberpunk
import yaml
from datetime import datetime, timedelta
import os
import json
from telegram.ext import Updater, JobQueue, CommandHandler, Application
from telegram import Bot
from typing import List, Tuple, Dict


# Funções Auxiliares


def take_data(tickers: List[str]) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Downloads and processes market data for the provided tickers using yfinance.
    """
    market_data = yf.download(tickers, period="6mo")["Adj Close"].dropna()
    daily_returns = market_data.pct_change()

    returns = {
        ticker: f"{round(daily_returns[ticker].iloc[-1] * 100, 2)}%"
        for ticker in tickers
    }

    return market_data, returns


def generate_graphs(
    data: pd.DataFrame, tickers: List[str], graph_dir: pathlib.Path
) -> None:
    """
    Generates and saves line graphs for each ticker in the provided data.
    """
    plt.style.use("cyberpunk")

    # Ajustar os dados para o último mês
    data.index = data.index.tz_localize(None)
    data_start = datetime.now() - timedelta(days=31)
    temp_data = data.loc[data.index >= data_start]

    for ticker in tickers:
        fig, ax = plt.subplots(figsize=(16, 16))
        ax.plot(temp_data[ticker])
        ax.set_title(ticker)
        plt.savefig(graph_dir.joinpath(f"{ticker.lower()}.png"), dpi=300)
        plt.clf()
        plt.close(fig)


async def send_telegram_message(api_token, chat_id, text):
    application = Bot(token=api_token)
    await application.send_message(chat_id=chat_id, text=text)


def send_email(
    subject: str,
    html_content: str,
    image_paths: List[str],
    image_cids: List[str],
    recipients: List[str],
    message: str,
) -> None:
    """
    Sends an email with the specified subject, HTML content, and attached images.
    """
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["To"] = ", ".join(recipients)
    msg["From"] = "vicenters10@gmail.com"
    msg.attach(MIMEText(html_content, "html"))

    for image_path, cid in zip(image_paths, image_cids):
        with open(image_path, "rb") as img_file:
            image = MIMEImage(img_file.read())
        image.add_header("Content-ID", f"<{cid}>")
        msg.attach(image)

    try:
        SOME_SECRET = os.environ["SOME_SECRET"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
            smtp_server.login("vicenters10@gmail.com", SOME_SECRET)
            smtp_server.sendmail("vicenters10@gmail.com", recipients, msg.as_string())
    except Exception as e:
        print(f"Error sending email: {e}")

    try:
        # Configurações do Telegram
        api_token = os.getenv("TELEGRAM_API_TOKEN")  # Insira o token do bot
        chat_id = os.getenv("CHAT_ID")

        # Inicializa o bot
        send_telegram_message(api_token, chat_id, message)
    except Exception as e:
        print(f"Error sending message: {e}")


def get_ticker_name(ticker: str) -> str:
    """
    Gets the full name of the asset from a given ticker symbol.
    """
    return yf.Ticker(ticker).info.get("longName", ticker)


def generate_data_dict(tickers: List[str], returns: Dict[str, str]) -> Dict:
    """
    Generates the dictionary to be used for email template rendering.
    """
    data_dict = {
        "data": datetime.now().strftime("%d/%m/%Y"),
        "infos": [],
    }

    for ticker in tickers:
        info = {
            "ativo": get_ticker_name(ticker),
            "descricao": f"O retorno do {ticker} foi",
            "retorno": returns[ticker],
            "color": "green" if float(returns[ticker].replace("%", "")) > 0 else "red",
            "cid_grafico": f"{ticker.lower()}.png",
        }
        data_dict["infos"].append(info)

    return data_dict


def generate_data_json(
    tickers: List[str],
    returns: Dict[str, str],
    output_path: str = "docs/ticker_data.json",
) -> None:
    """
    Generates a JSON file with ticker data.
    """
    data = {
        ticker: {
            "ticker": ticker,
            "ticker_fullname": get_ticker_name(ticker),
            "ticker_graph_path": f"../graphs/{ticker.lower()}.png",
            "ticker_return": returns[ticker],
        }
        for ticker in tickers
    }

    with open(output_path, "w") as json_file:
        json.dump(data, json_file)


def load_tickers_from_yaml(yaml_file: str) -> List[str]:
    """
    Loads the list of tickers from a YAML file.
    """
    with open(yaml_file, "r") as file:
        return yaml.safe_load(file).get("tickers", [])


def generate_message(
    date: str, tickers: List[str], returns: Dict[str, str], market_data: pd.DataFrame
) -> str:
    message = f"*** Relatório {date} ***\n"

    data_start = datetime.now() - timedelta(days=2)
    data = market_data.iloc[market_data.index > data_start]

    for ticker in tickers:
        # Fechamento de hoje (última linha de market_data)
        today_close = market_data[ticker].iloc[-1]

        # Fechamento do dia anterior (penúltima linha de market_data)
        yesterday_close = market_data[ticker].iloc[-2]

        message += f"Ativo: {ticker}\n"
        message += f"\t- Retorno: {returns[ticker]}\n"
        message += f"\t- Fechamento de Hoje: {today_close:.2f}\n"
        message += f"\t- Fechamento de Ontem: {yesterday_close:.2f}\n\n"

    return message


# Função Principal
def main() -> None:
    """
    Main function to process data, generate graphs, get news, and send an email report.
    """
    # Carregar tickers
    tickers = load_tickers_from_yaml(pathlib.Path("src/tickers.yaml"))

    # Obter dados e gerar gráficos
    market_data, returns = take_data(tickers)
    graph_dir = pathlib.Path("graphs")
    graph_dir.mkdir(exist_ok=True)
    generate_graphs(market_data, tickers, graph_dir)

    # Preparar os dados para o email
    data_dict = generate_data_dict(tickers, returns)
    generate_data_json(tickers, returns)

    # Renderizar template HTML
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("index.html")
    html_content = template.render(data_dict)

    # Gerar mensagem do telegram
    message = generate_message(data_dict["data"], tickers, returns, market_data)

    # Definir detalhes do email e enviar
    subject = f"Relatório da bolsa do dia {data_dict['data']}"
    recipients = ["vicenters10@gmail.com"]
    image_paths = [f"graphs/{ticker.lower()}.png" for ticker in tickers]
    image_cids = [f"{ticker.lower()}.png" for ticker in tickers]
    send_email(subject, html_content, image_paths, image_cids, recipients, message)


if __name__ == "__main__":
    main()
