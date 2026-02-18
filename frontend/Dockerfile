FROM node:25.2.1

WORKDIR /app

COPY package*.json /app/
RUN npm install

# Keep a baseline copy; compose mount will provide live files during dev.
COPY . /app

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
