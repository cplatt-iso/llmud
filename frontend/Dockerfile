FROM nginx:alpine
# Remove default Nginx welcome page
RUN rm /usr/share/nginx/html/index.html
# Copy our amazing frontend files
COPY ./src /usr/share/nginx/html
EXPOSE 80