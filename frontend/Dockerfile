FROM node:25.2.1

WORKDIR /app

# Copy workspace root package.json and all package.json files for install layer caching
COPY package*.json /app/
COPY packages/shared/package.json /app/packages/shared/
COPY packages/trade/package.json /app/packages/trade/
COPY packages/admin/package.json /app/packages/admin/
COPY packages/misc/package.json /app/packages/misc/

RUN npm install && chown -R node:node /app

# Keep a baseline copy; compose mount will provide live files during dev.
COPY --chown=node:node . /app

USER node

EXPOSE 5173 5174 5175

CMD ["sh", "-c", "npm install && (npm run dev:trade & npm run dev:admin & npm run dev:misc & wait)"]
