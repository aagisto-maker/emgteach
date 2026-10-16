---
marp: true
theme: uncover
class: invert
paginate: true
backgroundColor: #0f172a
color: #e2e8f0
style: |
  section {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    text-align: left;
    padding: 45px 65px;
    font-size: 24px;
  }
  h1 {
    color: #38bdf8;
    font-size: 1.8rem;
    margin-bottom: 0.8rem;
    border-bottom: 2px solid #334155;
    padding-bottom: 0.3rem;
  }
  h2 {
    color: #94a3b8;
    font-size: 1.2rem;
    font-weight: 400;
  }
  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-top: 15px;
  }
  .grid-3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 18px;
    margin-top: 15px;
  }
  .card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 18px 22px;
  }
  .card-highlight {
    background: #1e293b;
    border: 2px solid #38bdf8;
    border-radius: 12px;
    padding: 18px 22px;
  }
  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .badge-blue { background: #0284c7; color: #fff; }
  .badge-amber { background: #d97706; color: #fff; }
  .badge-green { background: #059669; color: #fff; }
  .badge-red { background: #dc2626; color: #fff; }
  .timeline {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin-top: 25px;
  }
  .timeline-step {
    flex: 1;
    background: #1e293b;
    border-top: 4px solid #38bdf8;
    border-radius: 8px;
    padding: 14px;
    font-size: 0.85rem;
    text-align: center;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    margin-top: 10px;
  }
  th {
    background: #1e293b;
    color: #38bdf8;
    border: 1px solid #334155;
    padding: 10px;
  }
  td {
    border: 1px solid #334155;
    padding: 10px;
  }
---

<!-- _class: invert lead -->
# Neurotransmisión Sináptica
## Fisiopatología, Biofísica y Resolución Clínica

**Módulo:** Neurofisiología Médica  
*Estudio interactivo de la placa motora*

<!-- 
NOTAS DEL ORADOR:
Bienvenidos. Hoy abordaremos la neurotransmisión sináptica integrando la biofísica de canales y receptores directamente con la deducción diagnóstica. Nuestro objetivo es responder qué sucede a nivel molecular cuando una paciente joven comienza a claudicar físicamente con el uso repetitivo.
-->

---

# 1. Caso Clínico Inicial
## La paciente que se cansa de mirar

<div class="grid-2">
  <div class="card">
    <span class="badge badge-amber">Hallazgos Cardinales</span>
    <p>• <b>Perfil:</b> Mujer, 28 años.</p>
    <p>• <b>Patrón:</b> Ptosis y diplopía vespertina.</p>
    <p>• <b>Signo clave:</b> Fatiga tras uso repetido; alivio en reposo.</p>
    <p>• <b>Examen:</b> Reflejos y sensibilidad 100% conservados.</p>
  </div>
  <div class="card-highlight">
    <span class="badge badge-blue">Pregunta Central</span>
    <p><b>¿Dónde radica la falla primaria?</b></p>
    <p>⚡ <b>¿El Cable?</b> (Axón / Conducción)</p>
    <p>🔄 <b>¿La Interfaz?</b> (Sinapsis / Placa Motora)</p>
    <p>⚙️ <b>¿El Motor?</b> (Fibra muscular / Actina-Miosina)</p>
  </div>
</div>

<!-- 
NOTAS DEL ORADOR:
Iniciamos con una paciente de 28 años sin antecedentes relevantes. Consulta por debilidad fluctuante que empeora en la tarde. Al fijar la mirada hacia arriba presenta caída palpebral y visión doble. Al descansar, recupera la fuerza. Noten que la sensibilidad y los reflejos osteotendinosos están íntegros, lo cual descarta una neuropatía sensorial o motora básica. La gran interrogante: ¿falla el cable conductor, el motor de la fibra muscular, o la interfaz química en la placa motora?
-->

---

# 2. Infraestructura
## Sinapsis Eléctrica vs. Sinapsis Química

<div class="grid-2">
  <div class="card">
    <span class="badge badge-blue">Sinapsis Eléctrica (El Puente)</span>
    <p>• <b>Estructura:</b> Uniones gap (conexones).</p>
    <p>• <b>Cinética:</b> Instantánea (~0.2 ms).</p>
    <p>• <b>Flujo:</b> Bidireccional.</p>
    <p>• <b>Objetivo:</b> Sincronización masiva (miocardio, interneuronas).</p>
  </div>
  <div class="card">
    <span class="badge badge-green">Sinapsis Química (La Computadora)</span>
    <p>• <b>Estructura:</b> Hendidura (20–40 nm) + vesículas.</p>
    <p>• <b>Cinética:</b> Retardo sináptico (0.5–1.0 ms).</p>
    <p>• <b>Flujo:</b> Estrictamente unidireccional.</p>
    <p>• <b>Objetivo:</b> Plasticidad, amplificación y diana farmacológica.</p>
  </div>
</div>

<!-- 
NOTAS DEL ORADOR:
La sinapsis eléctrica conecta citoplasmas mediante conexinas; no hay retardo y permite sincronizar poblaciones enteras al unísono. La sinapsis química introduce una distancia física que impone un retardo fisiológico por exocitosis y difusión. No obstante, a cambio de unos milisegundos ganamos plasticidad, computación de señal, modulación graduada y sitios de intervención médica y farmacológica.
-->

---

# 3. El Ciclo Sináptico
## Las 5 Fases de la Señal Neuroquímica

<div class="timeline">
  <div class="timeline-step">
    <b>1. Síntesis</b><br>
    Precursores enzimáticos en soma/axón
  </div>
  <div class="timeline-step">
    <b>2. Empaque</b><br>
    Gradiente H+-ATPasa (VAChT, VMAT)
  </div>
  <div class="timeline-step">
    <b>3. Liberación</b><br>
    Entrada de Ca2+ voltaje-dependiente
  </div>
  <div class="timeline-step">
    <b>4. Acción</b><br>
    Unión a receptor postsináptico
  </div>
  <div class="timeline-step">
    <b>5. Inactivación</b><br>
    Recaptación o lisis (AChE)
  </div>
</div>

<div class="card" style="margin-top: 20px;">
  <span class="badge badge-amber">Regla Biológica</span>
  <span>Para considerarse neurotransmisor debe sintetizarse en la terminal, liberarse por Ca2+, reproducir el efecto fisiológico y eliminarse activamente. (Excepción: mensajeros retrógrados gaseosos como el NO).</span>
</div>

<!-- 
NOTAS DEL ORADOR:
El ciclo consta de 5 fases universales. El empaquetamiento requiere gradientes de protones generados activamente por ATPasas. La liberación es estrictamente calcio-dependiente. La inactivación es obligatoria: si el neurotransmisor persistiera indefinidamente en la hendidura, provocaría la desensibilización del receptor o toxicidad celular.
-->

---

# 4. Fusión Sináptica: Maquinaria SNARE
## Dianas Críticas de las Neurotoxinas

<div class="grid-2">
  <div class="card">
    <span class="badge badge-blue">Cremallera Molecular</span>
    <p>• <b>v-SNARE:</b> Sinaptobrevina (en vesícula).</p>
    <p>• <b>t-SNARE:</b> Sintaxina-1 y SNAP-25 (membrana).</p>
    <p>• <b>Sensor Ca2+:</b> Sinaptotagmina-1 (gatillo en <1 ms).</p>
    <p><i>Mecánica: Cuatro hélices enrolladas vencen la repulsión electrostática.</i></p>
  </div>
  <div class="card">
    <span class="badge badge-red">Ataque Clostridial</span>
    <p>• <b>Toxina Botulínica:</b> Corta SNARE periférico → Bloquea ACh → <b>Parálisis Flácida</b>.</p>
    <p>• <b>Toxina Tetánica:</b> Migración retrógrada a médula → Corta SNARE en Renshaw → Bloquea GABA/Gly → <b>Parálisis Espástica</b>.</p>
  </div>
</div>

<!-- 
NOTAS DEL ORADOR:
Para fusionar dos bicapas lipídicas con cargas negativas se requiere el motor SNARE. La sinaptobrevina vesicular se trenza con SNAP-25 y sintaxina. La sinaptotagmina sujeta el complejo hasta que detecta el ion calcio. Noten el contraste clínico: el botulismo paraliza por falta de acetilcolina en la unión muscular; el tétanos produce espasmos severos porque inhibe a las interneuronas inhibidoras del asta anterior medular.
-->

---

# 5. Receptores: Ionotrópicos vs. Metabotrópicos
## Velocidad de Canal vs. Cascada de Señalización

<div class="grid-3">
  <div class="card">
    <span class="badge badge-blue">Ionotrópico</span>
    <p><b>El Canal Rápido</b></p>
    <p>• Latencia: 1–10 ms.</p>
    <p>• Efecto: Fásico y breve.</p>
    <p>• <i>Ejemplos:</i> Nicotínico (ACh), GABAA, AMPA/NMDA.</p>
  </div>
  <div class="card">
    <span class="badge badge-amber">Metabotrópico</span>
    <p><b>La Cascada</b></p>
    <p>• Latencia: Segundos a min.</p>
    <p>• Acoplado a Proteínas G (Gs, Gi, Gq).</p>
    <p>• <i>Ejemplos:</i> Muscarínicos (ACh), D1-D5, Adrenérgicos.</p>
  </div>
  <div class="card">
    <span class="badge badge-green">Termostato Local</span>
    <p><b>Regulación</b></p>
    <p>• <b>Autorreceptor:</b> Freno presináptico por retroalimentación.</p>
    <p>• <b>Heterorreceptor:</b> Modulación cruzada intersináptica.</p>
  </div>
</div>

<!-- 
NOTAS DEL ORADOR:
Los ionotrópicos forman el propio poro iónico y responden de inmediato. Los metabotrópicos amplifican la señal mediante segundos mensajeros y cascadas de fosforilación intracelular. En la terminal presináptica, los autorreceptores actúan como termostatos para impedir la depleción y toxicidad por exceso de neurotransmisor.
-->

---

# 6. Circuitos: Precisión vs. Proyección Difusa
## Redes Cableadas y Sistemas Moduladores del SNC

<div class="grid-2">
  <div class="card">
    <span class="badge badge-blue">Sistemas Cableados (Punto a Punto)</span>
    <p>• <b>Mediadores:</b> Glutamato (+) y GABA (-).</p>
    <p>• <b>Arquitectura:</b> Conexiones discretas y topográficas.</p>
    <p>• <b>Función:</b> Procesamiento sensorial discriminativo, computación cortical y control motor milimétrico.</p>
  </div>
  <div class="card">
    <span class="badge badge-amber">Sistemas de Radiación Difusa</span>
    <p>• <b>Mediadores:</b> Dopamina, NA, Serotonina, ACh central.</p>
    <p>• <b>Arquitectura:</b> Núcleos del tronco (Locus coeruleus, Rafe) con amplias varicosidades axonales.</p>
    <p>• <b>Función:</b> Regulación del tono global, afecto, vigilia y motivación.</p>
  </div>
</div>

<!-- 
NOTAS DEL ORADOR:
El sistema cableado opera como fibra óptica: conexiones punto a punto milimétricas mediadas por aminoácidos neurotransmisores. Los sistemas de radiación difusa son como antenas de radio: pocos somas en el tronco encefálico modulan redes enteras mediante transmisión de volumen sobre receptores metabotrópicos, regulando el estado cerebral general.
-->

---

# 7. Resolución: Miastenia Gravis
## Cuando claudica el factor de seguridad

<div class="grid-2">
  <div class="card-highlight">
    <span class="badge badge-red">Fisiopatología Molecular</span>
    <p>• <b>Diana:</b> Autoanticuerpos anti-AChR (~85%) o anti-MuSK.</p>
    <p>• <b>Daño:</b> Destrucción de pliegues postsinápticos.</p>
    <p>• <b>Mecanismo de fatiga:</b> Al haber menos receptores, la caída fisiológica normal de ACh por pulso hace que el potencial caiga bajo el umbral de disparo.</p>
  </div>
  <div class="card">
    <span class="badge badge-green">Confirmación y Terapéutica</span>
    <p>• <b>EMG 3 Hz:</b> Caída decremental >10% del PAMC.</p>
    <p>• <b>Fibra aislada:</b> Jitter patológicamente aumentado.</p>
    <p>• <b>Tratamiento:</b> Inhibidores de AChE (Piridostigmina) → Prolonga ACh en hendidura.</p>
  </div>
</div>

<!-- 
NOTAS DEL ORADOR:
Resolución del caso: la paciente tiene Miastenia Gravis. Sus anticuerpos destruyen receptores nicotínicos postsinápticos. Normalmente liberamos suficiente acetilcolina para superar con holgura el umbral; esto se llama 'factor de seguridad'. Al reducirse los receptores, con cada estímulo consecutivo la depleción fisiológica normal deja de alcanzar el umbral, provocando el bloqueo y la fatigabilidad vespertina. La piridostigmina compensa esto evitando la degradación de la poca ACh disponible.
-->

---

# 8. Síntesis Integradora
## Diagnóstico Diferencial de la Placa Motora

| Patología | Diana Molecular | Patrón EMG | Rasgo Clínico Clave |
| :--- | :--- | :--- | :--- |
| **Miastenia Gravis** | Receptor AChR *(Postsináptica)* | **Decremento** a baja frecuencia (3 Hz) | Fatiga ocular/bulbar; empeora con uso continuo |
| **Lambert-Eaton** | Canales Ca2+ P/Q *(Presináptica)* | **Incremento (>100%)** a alta frecuencia | Debilidad proximal; mejora brevemente tras esfuerzo; disautonomía |
| **Botulismo** | Proteínas SNARE *(Presináptica)* | PAMC basal muy bajo | Parálisis flácida descendente rápida y midriasis arreactiva |

<!-- 
NOTAS DEL ORADOR:
Esta tabla resume el razonamiento clínico diferencial. Si la falla es postsináptica (Miastenia), hay decremento con el uso. Si es presináptica por bloqueo de canales de calcio (Lambert-Eaton), la estimulación repetida acumula calcio y facilita transitoriamente la respuesta (incremento patognomónico). Si las proteínas SNARE son escindidas (Botulismo), la exocitosis se anula de forma aguda.
-->
