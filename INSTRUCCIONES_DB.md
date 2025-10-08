# Instrucciones para levantar la base de datos PostgreSQL en un contenedor Docker

1. Asegúrate de tener Docker instalado y corriendo en tu sistema.

2. Ve a la carpeta del proyecto donde está el archivo `docker-compose.yml`.

3. Levanta el contenedor de la base de datos ejecutando:

```
docker-compose up -d db
```

Esto descargará la imagen oficial de PostgreSQL y levantará el contenedor con los siguientes parámetros:
- Base de datos: tutor_db
- Usuario: tutor_user
- Contraseña: tutor_pass
- Puerto local: 5432

4. (Opcional) Para ver los logs del contenedor:
```
docker-compose logs -f db
```

5. (Opcional) Para detener el contenedor:
```
docker-compose down
```

6. Puedes conectarte a la base de datos desde tu máquina local usando un cliente como DBeaver, TablePlus, o la terminal:

```
psql -h localhost -U tutor_user -d tutor_db
```
(La contraseña es `tutor_pass`)


8. (Opcional) Acceso web a la base de datos con pgAdmin:

Puedes levantar pgAdmin (interfaz web para PostgreSQL) en otro contenedor Docker y conectarlo a tu base de datos.

Ejecuta:
```
docker run -d \
	--name pgadmin \
	-e PGADMIN_DEFAULT_EMAIL=admin@admin.com \
	-e PGADMIN_DEFAULT_PASSWORD=admin \
	-p 5050:80 \
	dpage/pgadmin4
```

Luego accede a http://localhost:5050 con el usuario y contraseña definidos arriba.

Para conectar tu base de datos desde pgAdmin:
	- Host: db (si usas docker-compose) o localhost (si es standalone)
	- Puerto: 5432
	- Usuario: tutor_user
	- Contraseña: tutor_pass
	- Base de datos: tutor_db

También puedes agregar el servicio de pgAdmin a tu archivo docker-compose.yml:

```
	pgadmin:
		image: dpage/pgadmin4
		container_name: pgadmin
		environment:
			PGADMIN_DEFAULT_EMAIL: admin@admin.com
			PGADMIN_DEFAULT_PASSWORD: admin@admin.com
		ports:
			- "5050:80"
		depends_on:
			- db
```

Así podrás administrar la base de datos desde la web fácilmente.

---

Cuando quieras agregar más servicios (Qdrant, la app, etc.), solo agrégalos al mismo archivo `docker-compose.yml` y repite el proceso.
