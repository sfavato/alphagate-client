# Stage 1: Build the application
FROM python:3.10-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
# 🔴 AVANT : COPY ./app /app
# 🟢 APRÈS : On copie DANS un sous-dossier 'app'
COPY ./app /app/app

# Stage 2: Create the final image
FROM python:3.10-slim

WORKDIR /app

# Copy installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy application code
# 🔴 AVANT : COPY --from=builder /app /app
# 🟢 APRÈS : On récupère le sous-dossier 'app' complet
COPY --from=builder /app/app /app/app

# Expose the port the app runs on
EXPOSE 8000

# Run the application (Celle-ci est déjà correcte grâce à votre fix précédent)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]