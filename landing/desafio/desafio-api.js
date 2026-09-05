/* Cliente da API do Desafio Postaria Mais.
   Compartilhado por todas as paginas de /desafio/. */

const API_BASE = location.hostname === "localhost" || location.hostname === "127.0.0.1"
  ? "http://127.0.0.1:8077/desafio/api"
  : "https://app.thecreatorsclub.com.br/desafio/api";

const TOKEN_KEY = "desafio_token";
const PARTICIPANTE_KEY = "desafio_participante";
const ESTADO_KEY = "desafio_estado";

const Auth = {
  get token() {
    try { return localStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; }
  },
  get participante() {
    try { return JSON.parse(localStorage.getItem(PARTICIPANTE_KEY) || "null"); } catch { return null; }
  },
  salvar(token, participante) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(PARTICIPANTE_KEY, JSON.stringify(participante));
      // Quem entra agora nao pode herdar o estado de quem usou o aparelho antes.
      localStorage.removeItem(ESTADO_KEY);
    } catch {}
  },
  sair() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(PARTICIPANTE_KEY);
      localStorage.removeItem(ESTADO_KEY);
    } catch {}
    location.href = "login.html";
  },
};

/* Ultimo estado conhecido, guardado no navegador.

   A API mora em outro dominio, entao toda chamada autenticada paga um
   preflight antes do GET: sao dois ida e volta ate o primeiro dado chegar.
   Guardar o estado deixa a tela pintar na hora com o que ja se sabe, e a
   rede so confirma depois. O cache sai junto com o token no logout, senao a
   proxima pessoa que entrar nesse aparelho veria os dados da anterior. */
const Cache = {
  get estado() {
    try { return JSON.parse(localStorage.getItem(ESTADO_KEY) || "null"); } catch { return null; }
  },
  salvarEstado(estado) {
    try { localStorage.setItem(ESTADO_KEY, JSON.stringify(estado)); } catch {}
  },
};

function iniciaisDoNome(nome) {
  const partes = (nome || "").trim().split(/\s+/);
  return ((partes[0]?.[0] || "") + (partes[1]?.[0] || "")).toUpperCase() || "··";
}

/* Preenche nome e avatar do topo sem esperar a rede: esses dois ja estao no
   navegador desde o login. Devolve a participante pra quem quiser usar. */
function pintarIdentidade() {
  const eu = Auth.participante;
  if (!eu) return null;
  const primeiroNome = (eu.nome || "").split(" ")[0];
  document.querySelectorAll("[data-nome]").forEach((el) => { el.textContent = primeiroNome; });
  document.querySelectorAll("[data-avatar]").forEach((el) => { el.textContent = iniciaisDoNome(eu.nome); });
  return eu;
}

/* Chama a API. Em 401 manda pro login em vez de deixar a tela quebrada. */
async function api(caminho, { metodo = "GET", corpo = null, publico = false } = {}) {
  const headers = {};
  if (corpo) headers["Content-Type"] = "application/json";
  if (!publico && Auth.token) headers["Authorization"] = `Bearer ${Auth.token}`;

  let resposta;
  try {
    resposta = await fetch(`${API_BASE}${caminho}`, {
      method: metodo,
      headers,
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
  } catch {
    throw new Error("Não consegui falar com o servidor. Confere sua conexão.");
  }

  if (resposta.status === 401 && !publico) {
    Auth.sair();
    throw new Error("Sessão expirada.");
  }

  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || "Não deu certo. Tenta de novo.");
  return dados;
}

/* Redireciona pro login quem ainda nao entrou. Use no topo das paginas
   internas, antes de tentar carregar qualquer dado. */
function exigirLogin() {
  if (!Auth.token) {
    location.href = "login.html";
    return false;
  }
  return true;
}
