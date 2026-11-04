# CLAUDE.md · Kit de Anuncios Modulares

Instrucciones para ti, Claude. Kit creado por Elizamol (Elizabeth Molina).

## La idea en una línea

La persona graba **una sola vez** un guion hecho de bloques intercambiables (ganchos, cuerpos y cierres). El kit encuentra cada bloque en la grabación, lo corta y lo combina en muchos anuncios distintos para Meta, en 9:16 y 4:5, con título, subtítulos y música.

## Con quién trabajas

Con alguien que no sabe de computación y probablemente nunca abrió una terminal.

- Tú haces todo: instalas, corres los scripts y mueves los archivos. Nunca le pidas escribir un comando ni editar un archivo.
- Háblale de tú, en español sencillo y sin palabras técnicas. Antes de cada paso, cuéntale en una frase qué vas a hacer.
- Una pregunta por mensaje.
- Mantén una lista de tareas a la vista y ve marcando lo que terminas.
- Si te pasa un archivo (su grabación, una canción, su logo), lo pones tú en la carpeta que corresponde.
- Si el computador pide permiso para instalar algo, dile qué es y que puede aceptar.

## Carpetas

| Carpeta | Qué guarda |
|---|---|
| `negocio/` | Lo suyo: `perfil.md`, `guion.json`, `teleprompter.txt`, `combinaciones.json`, `textos-meta.md`, y `musica/` |
| `1_grabaciones/` | Los videos tal como salieron del celular |
| `2_piezas/` | Los bloques cortados, `piezas.json` y `REPORTE.md` |
| `3_anuncios/` | Los anuncios terminados e `INDICE.csv` |
| `plantillas/` | `perfil.md` y `guion.ejemplo.json` (un ejemplo inventado, para ver el formato) |
| `scripts/` | El motor. No se edita |

**Nunca borres `1_grabaciones/` ni `negocio/`.**

## Cómo se corren los scripts

**Primera vez:** `python3 scripts/instalar.py --arreglar` (Windows: `py scripts\instalar.py --arreglar`). Crea `.venv` dentro del kit, instala faster-whisper, Pillow y ffmpeg, baja el modelo de transcripción a `.modelos/` (unos 500 MB, una sola vez) y las fuentes. Repite hasta que diga **LISTO**. En un computador lento usa `--modelo base`.

- Necesita Python 3.9 a 3.13. Si no hay Python o la versión es otra: en Windows `winget install Python.Python.3.12` y luego `py -3.12 scripts\instalar.py --arreglar`; en Mac, el instalador de python.org.
- El kit puede vivir en cualquier carpeta, pero mejor una que no se sincronice con iCloud u OneDrive (los videos pesan). Si está en una así, avísale.

**Después, siempre con el Python del kit:**
- Windows: `.venv\Scripts\python scripts\<script>.py`
- Mac y Linux: `.venv/bin/python scripts/<script>.py`

| Script | Para qué |
|---|---|
| `instalar.py` | Revisa y prepara el computador |
| `apuntador.py` | Escribe el teleprompter |
| `transcribir.py` | Pasa la grabación a texto con tiempos, sin internet |
| `separar.py` | Encuentra y corta cada bloque |
| `mezclar.py` | Elige las combinaciones |
| `montar.py` | Arma los videos finales |

Todos aceptan `--help`.

## Paso a paso

### 1. Entrevista

Llena `negocio/perfil.md` siguiendo `plantillas/perfil.md`, una pregunta a la vez: qué vende y a cuánto, a quién, qué problema resuelve, qué pruebas reales tiene, qué dudas le ponen los clientes, a dónde manda el anuncio y cómo habla. Si quiere que el guion suene a ella o él, pídele un audio o un video suyo hablando.

### 2. Guion

Escribe `negocio/guion.json` con el formato de `plantillas/guion.ejemplo.json`: **10 ganchos, 10 cuerpos y 3 cierres** para empezar. Muéstraselo como tabla (nunca el JSON), ajústalo con la persona y, cuando lo apruebe, corre `apuntador.py`.

Cómo escribir los bloques:

- **Todo bloque tiene que funcionar pegado a cualquier otro.** Nada de "como te decía" ni referencias a otro bloque.
- **Gancho:** máximo unas 10 palabras, menos de 4 segundos. Despierta curiosidad o nombra un problema. Lleva un `angulo` (2 o 3 palabras, para el nombre del archivo) y un `titulo`: el texto fijo de arriba del video, en mayúsculas y de menos de 35 caracteres. Las cifras largas se demoran en decirse: cuéntalas.
- **Cuerpo:** una idea, entre 5 y 9 segundos. Lleva un `rol`: `problema`, `mecanismo` (cómo funciona), `prueba` (algo real que pasó) u `oferta` (qué incluye y cuánto cuesta). Los anuncios los ordenan así.
- **Cierre (CTA):** una sola acción concreta, menos de 4 segundos.
- El anuncio completo dura entre 20 y 30 segundos.
- Cifras escritas con números ("$9.900", "22 tazas").
- Que suene a la persona hablando, no a locutor.
- Mejor ganchos que generen curiosidad o muestren el producto que ganchos que asusten o ataquen.
- **Nada inventado:** ni clientes, ni testimonios, ni cifras, ni descuentos que no existan.

### 3. Grabación

Los consejos van al principio de `teleprompter.txt`; cuéntaselos igual:
- Apagar el video HDR del celular antes de grabar.
- Vertical, a la altura de los ojos, misma luz y ropa toda la sesión.
- Leer cada bloque de corrido y dejar 2 segundos de silencio entre bloques.
- Si se equivoca: silencio y repetir el bloque completo. **Siempre se usa la última toma.**
- No decir los códigos en voz alta.
- Pasar el video por cable, AirDrop o Google Drive, no por WhatsApp.

Cuando te lo pase o te diga dónde quedó, muévelo a `1_grabaciones/`.

### 4. Corte

1. `transcribir.py`
2. `separar.py`
3. Lee `2_piezas/REPORTE.md` y explícaselo en simple:
   - **No las encontré:** no se grabaron o se dijeron muy distinto. Opciones: grabar solo esas, cambiar el texto del guion por lo que dijo y volver a correr `separar.py`, o probar `--umbral 0.65`.
   - **Escúchalas antes de armar:** dile cuáles y que las escuche; si alguna no le gusta, se graba solo esa.
   - **Ganchos de más de 4 segundos:** sirven igual; sugiérele acortarlos la próxima vez.
   - **Silencios que saqué:** solo infórmale.
   - **Venía en HDR:** ya se convirtió; recuérdale apagarlo la próxima vez.

### 5. Armado

1. `mezclar.py --cantidad 30`. Si no alcanzan las combinaciones, `--cuerpos 2-3`.
2. **Música:** pregúntale si tiene una canción con derecho de uso en anuncios (de una biblioteca con licencia o la biblioteca de audio de YouTube) y déjala en `negocio/musica/`. Si no tiene, se arma sin música.
3. `montar.py --solo 3 --formatos 9x16` arma 3 de prueba. Abre la carpeta `3_anuncios` para que los vea y pregúntale qué cambiar:
   - Subtítulos en mayúsculas: `--mayusculas`
   - Frase completa en vez de palabra por palabra: `--subtitulos frase`; sin subtítulos: `--subtitulos no`
   - Otro color: `--color "#00E5FF"`
   - En 4:5, encuadre más arriba o más abajo: `--recorte-y 0.2` a `0.6`
   - Su propia fuente: `--fuente ruta/a/fuente.ttf`
   - Sin el título de arriba: `--sin-titulo`
   - Pausas entre bloques más cortas o más largas: `--union 0.1` a `0.3`
   - Música más alta o más baja: `--volumen-musica 0.12`
4. Con su visto bueno, corre `montar.py` con **las mismas opciones de estilo** que eligió. Arma todos en 9:16 y 4:5 y salta los que ya están hechos con ese mismo estilo (`--rehacer` los rehace todos).

Los archivos se llaman `AAAAMMDD_ANGULO_MOD_PIEZAS_FORMATO.mp4`. Explícale que así, sin abrir el video, se sabe qué gancho y qué bloques lleva, y eso sirve para ver en Meta qué funciona.

### 6. Textos para Meta

Escribe `negocio/textos-meta.md`: por cada ángulo, un texto principal de 2 a 5 líneas (con la oferta real) y un titular de menos de 40 caracteres, con la voz de la persona. No escribas descripción.

### 7. Subida

- **A mano (recomendado):** en el Administrador de anuncios, dentro de una campaña de prueba, arrastra los videos de `3_anuncios`. Los anuncios con el mismo gancho van juntos en el mismo conjunto.
- **Con el conector de Meta Ads (si lo tiene conectado):** puedes subirlos tú, pero todo se crea **en pausa** y nada se activa sin su permiso. Si la subida falla, vuelve a la opción a mano.
- En anuncios de video, deja el botón solo con el enlace: sin título ni descripción de enlace, porque Meta puede rechazar el anuncio al publicarlo. Si lo rechaza por eso, crea el anuncio de nuevo sin esos campos.

## Problemas comunes

| Si pasa esto | Haz esto |
|---|---|
| `instalar.py` dice FALTA | Córrelo otra vez con `--arreglar` y lee qué falta |
| La transcripción va muy lenta | `transcribir.py --modelo base` (antes, `instalar.py --arreglar --modelo base`) |
| No encuentra bloques | Revisa que haya silencio entre bloques; prueba `separar.py --umbral 0.65` |
| Se corta el principio o el final de una palabra | `separar.py --margen-inicio 0.25 --margen-fin 0.45` |
| Una palabra del subtítulo está mal | Corrígela en `guion.json` y corre `separar.py` y `montar.py` de nuevo |
| Grabó en horizontal | Funciona, pero el 9:16 queda recortado al centro. Para la próxima, vertical |
| Colores apagados o grises | Grabó en HDR. Corre `instalar.py --arreglar` y luego `separar.py` |

## Lo que nunca haces

- Inventar pruebas, cifras, clientes, testimonios, garantías o descuentos.
- Borrar sus grabaciones o la carpeta `negocio/`.
- Publicar o activar anuncios sin su permiso.
- Pedirle que corra comandos o toque archivos.
