# Usar uma imagem Python oficial
FROM python:3.12-slim

# Definir o diretório de trabalho dentro do container
WORKDIR /app

# Copiar o arquivo pyproject.toml e o arquivo poetry.lock, se houver
COPY pyproject.toml poetry.lock* /app/

# Instalar o Poetry
RUN pip install poetry

# Instalar as dependências sem criar um ambiente virtual
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copiar o restante do código para dentro do container
COPY . /app

# Expor qualquer porta que o seu script precise (caso você precise, por exemplo, de um servidor rodando)
# Exemplo: EXPOSE 8000

# Definir a variável de ambiente para o Poetry (caso você use pyproject.toml)
ENV PYTHONUNBUFFERED=1

# Rodar o arquivo principal
CMD ["python", "main.py"]
