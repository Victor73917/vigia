// VIGÍA · analista IA (fase 8) · función de Supabase (Deno).
// La página de pruebas manda la conversación (el primer mensaje trae las reglas y el resumen de los datos de VIGÍA);
// esta función verifica el cupo diario, llama a Claude con la clave guardada como secreto ANTHROPIC_API_KEY y devuelve
// el texto. La clave nunca llega al navegador. No se guardan las preguntas ni las respuestas.
import Anthropic from "npm:@anthropic-ai/sdk";
import { createClient } from "npm:@supabase/supabase-js@2";

const MODELO = "claude-haiku-5-5";
const LIMITE_DIARIO = Number(Deno.env.get("ANALISTA_LIMITE_DIARIO") ?? "30");
const ORIGENES = ["https://victor73917.github.io", "http://localhost:8765"];
const MAX_MENSAJES = 9;
const MAX_PRIMERO = 200_000; // caracteres del primer mensaje (reglas + datos)
const MAX_OTROS = 4_000;

const SISTEMA = `Eres el analista de VIGÍA, un monitor de El Niño Costero, lluvias, ríos y emergencias en el Perú.
Responde en español, breve y claro, solo con los datos que vienen en la conversación, citando la fuente de cada dato
(SENAMHI, ENFEN, COEN-INDECI, GloFAS, ECMWF, NOAA). Si un dato no está, di «sin datos suficientes»; nunca lo inventes
ni digas que no hay riesgo por falta de datos. Si la pregunta no trata de esos temas, dilo en una frase.
Si alguien está en peligro, recuerda los números 105 (Policía), 116 (Bomberos), 106 (SAMU) y 115 (Defensa Civil).
Esta es una página de pruebas: aclara que no reemplaza los avisos oficiales.`;

const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

function cabeceras(origen: string | null): HeadersInit {
  return {
    "Access-Control-Allow-Origin": origen && ORIGENES.includes(origen) ? origen : ORIGENES[0],
    "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Content-Type": "application/json",
    "Vary": "Origin",
  };
}
const responder = (cuerpo: unknown, estado: number, origen: string | null) =>
  new Response(JSON.stringify(cuerpo), { status: estado, headers: cabeceras(origen) });

Deno.serve(async (req) => {
  const origen = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response("ok", { headers: cabeceras(origen) });
  if (req.method !== "POST") return responder({ error: "metodo" }, 405, origen);
  if (origen && !ORIGENES.includes(origen)) return responder({ error: "origen" }, 403, origen);
  if (!Deno.env.get("ANTHROPIC_API_KEY")) return responder({ error: "clave" }, 503, origen); // falta el secreto

  let mensajes: Anthropic.MessageParam[];
  try {
    const cuerpo = await req.json();
    mensajes = cuerpo?.mensajes;
    const valido = Array.isArray(mensajes) && mensajes.length >= 1 && mensajes.length <= MAX_MENSAJES &&
      mensajes.every((m, i) => (m?.role === "user" || m?.role === "assistant") && typeof m.content === "string" &&
        m.content.trim().length > 0 && m.content.length <= (i === 0 ? MAX_PRIMERO : MAX_OTROS)) &&
      mensajes[0].role === "user" && mensajes[mensajes.length - 1].role === "user";
    if (!valido) return responder({ error: "entrada" }, 400, origen);
  } catch {
    return responder({ error: "entrada" }, 400, origen);
  }

  const { data: quedan, error: errCupo } = await supabase.rpc("usar_analista", { p_limite: LIMITE_DIARIO });
  if (errCupo) return responder({ error: "servidor" }, 500, origen);
  if (quedan < 0) return responder({ error: "cupo", limite: LIMITE_DIARIO }, 429, origen);

  // el primer mensaje (reglas + datos de VIGÍA) es igual para todos durante una hora: se guarda en caché
  const [primero, ...resto] = mensajes;
  const entrada: Anthropic.MessageParam[] = [
    { role: "user", content: [{ type: "text", text: primero.content as string, cache_control: { type: "ephemeral" } }] },
    ...resto,
  ];

  try {
    const anthropic = new Anthropic(); // lee ANTHROPIC_API_KEY
    const r = await anthropic.messages.create({
      model: MODELO,
      max_tokens: 2000,
      system: SISTEMA,
      output_config: { effort: "low" },
      messages: entrada,
    });
    if (r.stop_reason === "refusal") return responder({ error: "rechazo", quedan }, 200, origen);
    const texto = r.content.filter((b) => b.type === "text").map((b) => b.text).join("\n").trim();
    return responder({ texto, quedan, cortada: r.stop_reason === "max_tokens", modelo: MODELO }, 200, origen);
  } catch (e) {
    if (e instanceof Anthropic.RateLimitError) return responder({ error: "limite_anthropic" }, 429, origen);
    if (e instanceof Anthropic.AuthenticationError || e instanceof Anthropic.PermissionDeniedError) {
      return responder({ error: "clave" }, 503, origen);
    }
    if (e instanceof Anthropic.BadRequestError && /credit|billing|balance/i.test(e.message)) {
      return responder({ error: "saldo" }, 503, origen);
    }
    console.error("analista", e instanceof Error ? e.message : e);
    return responder({ error: "servidor" }, 502, origen);
  }
});
