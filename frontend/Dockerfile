FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* is inlined at build time. It points at the backend as reached
# from the user's *browser* (i.e. the host-mapped port), not from inside the
# compose network — override with --build-arg for other deployments.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
