import { apiRequest } from "./client";

export async function resourceOptions(endpoint: string, labelKey = "name") {
  const options: { value: string; label: string }[] = [];
  let page = 1;
  let pages = 1;
  do {
    const data = await apiRequest<{ items: Record<string, unknown>[]; pages: number }>(`${endpoint}?page=${page}&limit=100`);
    pages = data.pages;
    for (const item of data.items) options.push({ value: String(item.id), label: String(item[labelKey] || item.email || item.uid || item.id) });
    page++;
  } while (page <= pages);
  return options;
}
