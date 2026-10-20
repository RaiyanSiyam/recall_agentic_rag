FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers /app/mcp-servers

ENV DATA_MODE=demo
ENV PYTHONPATH=/app/mcp-servers

EXPOSE 8003

CMD ["python", "mcp-servers/jira/server.py"]
