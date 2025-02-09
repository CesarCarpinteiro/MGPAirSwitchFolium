# Use the official Python image
FROM python:3.8-slim-buster

# Set the working directory
WORKDIR /app

# Copy the project files into the container
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the Flask app runs on
EXPOSE 3000

# Set the command to run the application
CMD ["python", "main.py"]