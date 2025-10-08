# Instrucciones para levantar Qdrant localmente con Docker

Qdrant es el vector database que usaremos para almacenar y consultar los embeddings de los documentos.

## Pasos rápidos

1. Asegúrate de tener Docker instalado y corriendo en tu sistema.

2. Ejecuta el siguiente comando en la terminal para levantar Qdrant en modo local (puertos por default):

```
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  qdrant/qdrant:latest
```

- El puerto 6333 es para la API HTTP (usada por LangChain y otros clientes).
- El puerto 6334 es para la API gRPC (opcional).

3. (Opcional) Para ver los logs del contenedor:
```
docker logs -f qdrant
```

4. (Opcional) Para detener y eliminar el contenedor:
```
docker stop qdrant && docker rm qdrant
```

5. (Opcional) Para persistencia de datos, puedes montar un volumen local:
```
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  qdrant/qdrant:latest
```

---

Una vez corriendo, Qdrant estará accesible en http://localhost:6333
