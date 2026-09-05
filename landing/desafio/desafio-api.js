/* Cliente da API do Desafio Postaria Mais.
   Compartilhado por todas as paginas de /desafio/. */

const API_BASE = location.hostname === "localhost" || location.hostname === "127.0.0.1"
  ? "http://127.0.0.1:8077/desafio/api"
  : "https://app.thecreatorsclub.com.br/desafio/api";

const TOKEN_KEY = "desafio_token";
const PARTICIPANTE_KEY = "desafio_participante";

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
    } catch {}
  },
  sair() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(PARTICIPANTE_KEY);
    } catch {}
    location.href = "login.html";
  },
};

/* Chama a API. Em 401 manda pro login em vez de deixar a tela quebrada. */
async function api(caminho, { metodo = "GET", corpo = null, publico = false } = {}) {
  const headers = { "Content-Type": "application/json" };
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
