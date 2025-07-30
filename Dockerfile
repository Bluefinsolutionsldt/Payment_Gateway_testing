# Use an official Python runtime as a parent image
FROM python:3.9

# Update system packages to fix vulnerabilities
RUN apt-get update && apt-get upgrade -y && apt-get clean

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project files into container
COPY . .

# Expose port (adjust if needed)
EXPOSE 8000

# Command to run app (change as needed)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
