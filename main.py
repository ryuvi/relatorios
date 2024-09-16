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
from typing import List, Tuple, Dict
import yaml
from datetime import datetime, timedelta
import os
import json


def take_data(tickers: List[str]) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    Downloads and processes market data for the provided tickers using yfinance.

    Args:
        tickers (List[str]): List of tickers to download market data for.

    Returns:
        Tuple[pd.DataFrame, Dict[str, str]]: DataFrame of the market data and a dictionary of returns for each ticker.
    """
    market_data = yf.download(tickers, period="6mo")
    market_data = market_data["Adj Close"].dropna()

    # Calculate daily returns
    daily_returns = market_data.pct_change()

    returns = {}
    for ticker in tickers:
        returns[ticker] = f"{round(daily_returns[ticker].iloc[-1] * 100, 2)}%"

    return market_data, returns


def generate_graphs(data: pd.DataFrame, tickers: List[str]) -> None:
    """
    Generates and saves line graphs for each ticker in the provided data.

    Args:
        data (pd.DataFrame): The market data.
        tickers (List[str]): List of tickers to generate graphs for.

    Returns:
        None
    """
    graph_path = pathlib.Path("graphs")
    graph_path.mkdir(exist_ok=True)

    plt.style.use("cyberpunk")

    temp_data = data
    temp_data.index = temp_data.index.tz_localize(None)
    data_start = datetime.utcnow() - timedelta(days=31)
    temp_data = temp_data.loc[temp_data.index >= data_start]

    for ticker in tickers:
        fig, ax = plt.subplots(figsize=(16, 16))
        ax.plot(temp_data[ticker])
        ax.set_title(ticker)
        plt.savefig(graph_path.joinpath(f"{ticker.lower()}.png"), dpi=300)
        plt.clf()
        plt.close(fig)


def get_news() -> List[Dict[str, str]]:
    """
    Fetches the top 5 financial news from Yahoo Finance RSS feed.

    Returns:
        List[Dict[str, str]]: A list of dictionaries containing news title, link, and image URL.
    """
    url = "https://finance.yahoo.com/news/rssindex"
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "lxml-xml")
    all_news = soup.find_all("item")[:5]

    formatted_news = []
    for news in all_news:
        formatted_news.append(
            {
                "title": news.find("title").text,
                "link": news.find("link").text,
                "image": (
                    news.find("media:content")["url"]
                    if news.find("media:content")
                    else ""
                ),
            }
        )
    return formatted_news


def send_email(
    subject: str,
    html_content: str,
    image_paths: List[str],
    image_cids: List[str],
    recipients: List[str],
) -> None:
    """
    Sends an email with the specified subject, HTML content, and attached images.

    Args:
        subject (str): Email subject.
        html_content (str): HTML content of the email.
        image_paths (List[str]): Paths to image files.
        image_cids (List[str]): Corresponding CIDs for inline images.
        recipients (List[str]): List of recipient email addresses.

    Returns:
        None
    """
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["To"] = ", ".join(recipients)
    msg["From"] = "vicenters10@gmail.com"
    msg.attach(MIMEText(html_content, "html"))

    for image_path, cid in zip(image_paths, image_cids):
        with open(image_path, "rb") as img_file:
            img_data = img_file.read()
        image = MIMEImage(img_data)
        image.add_header("Content-ID", f"<{cid}>")
        msg.attach(image)

    # Try to retrieve secret
    try:
        SOME_SECRET = os.environ["SOME_SECRET"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
            smtp_server.login(
                "vicenters10@gmail.com", SOME_SECRET
            )  # Insert your password here
            smtp_server.sendmail("vicenters10@gmail.com", recipients, msg.as_string())
    except Exception as e:
        print(f"An error ocurred:\n{e}")


def get_ticker_name(ticker: str) -> str:
    """
    Gets the full name of the asset from a given ticker symbol.

    Args:
        ticker (str): The ticker symbol.

    Returns:
        str: The full name of the asset.
    """
    ticker_data = yf.Ticker(ticker)
    info = ticker_data.info
    return info.get("longName", ticker)


def generate_data_dict(
    tickers: List[str], returns: Dict[str, str], news: List[Dict[str, str]]
) -> Dict:
    """
    Generates the dictionary to be used for email template rendering.

    Args:
        tickers (List[str]): List of tickers.
        returns (Dict[str, str]): Dictionary with the returns of each ticker.
        news (List[Dict[str, str]]): List of news articles.

    Returns:
        Dict: The data dictionary used for the template.
    """
    data_dict = {
        "data": datetime.now().strftime("%d/%m/%Y"),
        "infos": [],
        "news": news,
        "autor": "Ryuvi",
        "url_cancelamento": "URL_CANCELAMENTO",
        "url_relatorio": "URL_RELATORIO",
    }

    for ticker in tickers:
        ticker_name = get_ticker_name(ticker)
        info = {
            "ativo": ticker_name,
            "descricao": f"O retorno do {ticker} foi",
            "retorno": returns[ticker],
            "color": "green" if float(returns[ticker].replace("%", "")) > 0 else "red",
            "cid_grafico": f"{ticker.lower()}.png",
        }
        data_dict["infos"].append(info)

    return data_dict


def generate_data_json(tickers: List[str], returns: Dict[str, str]) -> None:
    """
    Generates a dictionary with the necessary data and saves it as a JSON file.

    Args:
        tickers (List[str]): List of tickers.
        returns (Dict[str, str]): Dictionary with the returns of each ticker.

    Returns:
        None
    """
    data = {}

    for ticker in tickers:
        ticker_name = get_ticker_name(ticker)
        info = {
            "ticker": ticker,
            "ticker_fullname": ticker_name,
            "ticker_graph_path": f"../graphs/{ticker.lower()}.png",
            "ticker_return": returns[ticker],
        }
        data[ticker] = info

    # Save the data as a JSON file
    with open("docs/ticker_data.json", "w") as json_file:
        json.dump(data, json_file)


def load_tickers_from_yaml(yaml_file: str) -> List[str]:
    """
    Loads the list of tickers from a YAML file.

    Args:
        yaml_file (str): Path to the YAML file.

    Returns:
        List[str]: List of tickers.
    """
    with open(yaml_file, "r") as file:
        data = yaml.safe_load(file)
        return data.get("tickers", [])


def main() -> None:
    """
    Main function to process data, generate graphs, get news, and send an email report.

    Returns:
        None
    """
    # Define the list of tickers
    files = os.listdir(".")
    target_file = "tickers.yaml"
    tickers = load_tickers_from_yaml(files[files.index(target_file)])

    # Fetch data and generate graphs
    market_data, returns = take_data(tickers)
    generate_graphs(market_data, tickers)
    news = get_news()

    # Prepare data for the email template
    data_dict = generate_data_dict(tickers, returns, news)

    generate_data_json(tickers, returns)

    # Render HTML template
    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("index.html")
    html_content = template.render(data_dict)

    # Define email details and send the email
    subject = f"Relatório da bolsa do dia {data_dict['data']}"
    recipients = ["vicenters10@gmail.com"]
    image_paths = [f"graphs/{ticker.lower()}.png" for ticker in tickers]
    image_cids = [f"{ticker.lower()}.png" for ticker in tickers]

    send_email(subject, html_content, image_paths, image_cids, recipients)


if __name__ == "__main__":
    main()
