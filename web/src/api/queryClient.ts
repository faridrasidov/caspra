import { QueryClient } from "@tanstack/vue-query";

export const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 15000, retry: 1, refetchOnWindowFocus: false } } });
