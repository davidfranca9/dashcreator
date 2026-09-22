// Caminho de um arquivo de public/ que funciona na raiz (Lovable) e em /hpc/ (site do clube).
export const asset = (caminho: string) =>
  /^https?:\/\//.test(caminho) ? caminho : import.meta.env.BASE_URL + caminho.replace(/^\//, "");
