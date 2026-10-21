FROM public.ecr.aws/awsguru/aws-lambda-adapter:1.0.0 AS lambda-adapter
FROM python:3.12-slim

WORKDIR /app

COPY --from=lambda-adapter /lambda-adapter /opt/extensions/lambda-adapter

ENV PORT=8000

COPY ./ ./

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-interval=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]