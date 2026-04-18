FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies first (separate layer — faster rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright's Chromium browser + all system dependencies it needs.
# playwright install --with-deps handles its own apt-get calls internally.
RUN playwright install chromium --with-deps

# Copy application source code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
