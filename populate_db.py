"""
Script para poblar la base de datos PostgreSQL con datos ficticios de estudiantes, materias y matrículas.
"""
import psycopg2

PG_HOST = "localhost"
PG_PORT = 5432
PG_DB = "tutor_db"
PG_USER = "tutor_user"
PG_PASSWORD = "tutor_pass"

def populate_db():
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )
    cur = conn.cursor()

    # Poblar tabla students
    students = [
        (1, 'Ana García', 'ana.garcia@email.com', 'ana123', 'Ingeniería Industrial', '3', 'es'),
        (2, 'Luis Pérez', 'luis.perez@email.com', 'luis456', 'Derecho', '4', 'es'),
        (3, 'María López', 'maria.lopez@email.com', 'maria789', 'Ingeniería Industrial', '2', 'es'),
    ]
    cur.executemany("""
        INSERT INTO students (id, name, email, password, career, grade, language)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING;
    """, students)

    # Poblar tabla subjects (insertar o actualizar)
    subjects = [
        (1, 'Investigación de Operaciones', '''# Plan de Estudio: Investigación de Operaciones (Ingeniería Industrial)

## Objetivos de Aprendizaje
- Comprender los fundamentos de la modelación matemática para la toma de decisiones.
- Aplicar técnicas de optimización lineal y no lineal a problemas reales de la industria.
- Desarrollar habilidades para interpretar resultados y evaluar escenarios.
- Implementar algoritmos básicos en software como Excel Solver, Python (PuLP, OR-Tools).

## Bloques de Conocimiento
1. **Introducción a la Investigación de Operaciones**
   - Definición, historia y aplicaciones en industria y servicios.
   - Metodología general de resolución de problemas.

2. **Programación Lineal (PL)**
   - Formulación de modelos.
   - Método Simplex.
   - Análisis de sensibilidad.

3. **Programación Entera y Mixta**
   - Problemas de asignación, transporte y localización.
   - Modelos de planeación de la producción.

4. **Programación No Lineal y Heurísticas**
   - Métodos de optimización no lineal.
   - Metaheurísticas: Algoritmos genéticos, recocido simulado.

5. **Teoría de Colas y Simulación**
   - Sistemas de espera.
   - Introducción a Monte Carlo.

6. **Toma de Decisiones Multicriterio**
   - Métodos AHP, TOPSIS.

## Alcance
- Se cubrirán **conceptos básicos e intermedios** de optimización y simulación.
- Quedan fuera: programación dinámica avanzada, optimización robusta y estocástica, teoría de juegos avanzada.

## Materiales Recomendados
- Hillier, F. & Lieberman, G. (2010). *Introduction to Operations Research* (McGraw Hill).
- Taha, H. (2017). *Operations Research: An Introduction* (Pearson).
- Recursos abiertos:
  - [MIT OpenCourseWare – Operations Research](https://ocw.mit.edu/courses/sloan-school-of-management/15-053-optimization-methods-in-management-science-spring-2013/)
  - [PDF: Introduction to Operations Research, Hillier](https://www.pdfdrive.com/introduction-to-operations-research-9th-edition-e158184909.html)
''', 'es'),
        (2, 'Derecho Internacional Público', '''# Plan de Estudio: Derecho Internacional Público (Derecho)

## Objetivos de Aprendizaje
- Comprender los principios fundamentales del Derecho Internacional.
- Analizar tratados, costumbre internacional y jurisprudencia de la Corte Internacional de Justicia (CIJ).
- Examinar el rol de los Estados, organizaciones internacionales y tribunales.
- Aplicar el marco jurídico internacional a casos prácticos (fronteras, derechos humanos, conflictos armados).

## Bloques de Conocimiento
1. **Fundamentos del Derecho Internacional Público**
   - Naturaleza jurídica.
   - Sujetos: Estados, organizaciones internacionales, individuos.

2. **Fuentes del Derecho Internacional**
   - Tratados internacionales.
   - Costumbre internacional.
   - Principios generales del derecho.

3. **Resolución de Controversias Internacionales**
   - Corte Internacional de Justicia.
   - Tribunales arbitrales.

4. **Derecho de los Tratados**
   - Convención de Viena.
   - Formación, validez y terminación de tratados.

5. **Derecho Internacional y Derechos Humanos**
   - Corte Interamericana de Derechos Humanos.
   - Naciones Unidas y protección de derechos.

6. **Uso de la Fuerza y Seguridad Internacional**
   - Carta de la ONU.
   - Conflictos armados y Derecho Internacional Humanitario.

## Alcance
- Se abordará **nivel introductorio e intermedio**, con enfoque en los tratados, sujetos y mecanismos de resolución de disputas.
- Quedan fuera: especializaciones en Derecho Penal Internacional, Comercio Internacional avanzado o Litigios arbitrales complejos.

## Materiales Recomendados
- Shaw, M. (2017). *International Law* (Cambridge University Press).
- Brownlie, I. (2008). *Principles of Public International Law* (Oxford).
- Recursos abiertos:
  - [UN Audiovisual Library of International Law](https://legal.un.org/avl/)
  - [PDF: International Law, Malcolm Shaw](https://www.pdfdrive.com/international-law-e199866433.html)
  - [Convención de Viena sobre el Derecho de los Tratados (ONU)](https://www.un.org/es/about-us/un-charter/full-text)
''', 'es'),
        (3, 'Producción Industrial', 'Procesos y gestión industrial', 'es'),
    ]
    for s in subjects:
        cur.execute("""
            INSERT INTO subjects (id, name, description, language)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                language = EXCLUDED.language;
        """, s)

    # Poblar tabla enrollments
    enrollments = [
        (1, 1),  # Ana García inscrita en Investigación de Operaciones
        (1, 3),  # Ana García inscrita en Producción Industrial
        (2, 2),  # Luis Pérez inscrito en Derecho Internacional Público
        (3, 1),  # María López inscrita en Investigación de Operaciones
    ]
    cur.executemany("""
        INSERT INTO enrollments (student_id, subject_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING;
    """, enrollments)

    conn.commit()
    cur.close()
    conn.close()
    print("Base de datos poblada con datos ficticios.")

if __name__ == "__main__":
    populate_db()
