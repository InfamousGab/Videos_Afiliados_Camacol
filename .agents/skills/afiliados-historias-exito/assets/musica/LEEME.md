# Banco de música de la serie

Deja aquí **cuatro pistas**. La skill elige una por capítulo a partir del nombre del
afiliado: parece azar entre capítulos, pero es siempre la misma para el mismo afiliado, así
que volver a renderizar no cambia la música. Para forzar una concreta, pon su ruta en
`proyecto.json`:

```json
"musica": { "pista": "insumos/otra-pista.mp3" }
```

## Qué pista sirve

- **Instrumental, sin voces.** Una voz cantada compite con la de la persona entrevistada.
- **Corporativa, de tempo estable**, sin cambios bruscos ni silencios largos: va a sonar
  agachada bajo el diálogo y cualquier salto se nota.
- **Mínimo 2:30.** Si es más corta se repite en bucle, y el punto de repetición se oye.
- **Poca energía entre 300 Hz y 3 kHz**, que es donde vive el habla. Una pista preciosa con
  mucho medio se pelea con la voz por mucho que se baje. `comprobar_mezcla.py` lo detecta.


Anota aquí de dónde salió cada pista y bajo qué licencia, para que quien reciba la serie lo
sepa sin tener que rastrearlo:

| Archivo | Origen | Licencia |
|---|---|---|
| Pista1.mp3 | | |
| Pista2.mp3 | | |
| Pista3.mp3 | | |
| Pista4.mp3 | | |
| Pista5.mp3 | | |
| Pista6.mp3 | | |
