<script setup lang="ts">

import { computed, onMounted, ref } from "vue";

import type { Schemas } from "../api/client";

import { portalRequest, refreshPortal, setPortalToken } from "../api/portal";

import { formatMoney, formatTime, amountInput } from "../utils/format";

import ActionDrawer, { type ActionField } from "../components/ActionDrawer.vue";

import DataState from "../components/DataState.vue";

import FormField from "../components/FormField.vue";

import TransactionTable from "../components/TransactionTable.vue";

import UiButton from "../components/UiButton.vue";



const loading = ref(true);

const busy = ref(false);

const error = ref("");

const tenant = ref("");

const email = ref("");

const password = ref("");

const invitation = ref("");

const self = ref<Schemas["CustomerWorkspace"] | null>(null);

const account = ref<Schemas["CustomerWorkspace"] | null>(null);

const selected = ref("");

const children = ref<{ id: string; name: string }[]>([]);

const payment = ref({ available: false, sandbox: false });

const packages = ref<Schemas["PackageOut"][]>([]);

const packageId = ref("");

const chosenPackage = computed(() => packages.value.find(p => p.id === packageId.value));

const checkout = ref<Schemas["CheckoutOut"] | null>(null);

const mode = ref<"topup" | "fund" | "limit" | "block" | null>(null);

const cardId = ref("");

const currency = computed(() => account.value?.wallets.find(w => w.type === "credit")?.currency ?? account.value?.wallets[0]?.currency ?? "USD");

const fields = computed<ActionField[]>(() => mode.value === "block" ? [{ key: "confirmation", label: "Type BLOCK to confirm" }] : mode.value === "limit" ? [{ key: "currency", label: "Currency", value: currency.value }, { key: "daily_minor", label: "Daily spending allowance", kind: "money" }] : [{ key: "currency", label: "Currency", value: chosenPackage.value?.currency ?? currency.value }, { key: "amount_minor", label: mode.value === "fund" ? "Paid credit to allocate" : "Top-up amount", kind: "money", value: mode.value === "topup" && chosenPackage.value ? amountInput(chosenPackage.value.paid_minor, chosenPackage.value.currency) : "" }]);

async function run(action: () => Promise<void>) { busy.value = true; error.value = ""; try { await action(); } catch (reason) { error.value = (reason as Error).message; } finally { busy.value = false; } }

async function loadAccount() { account.value = await portalRequest<Schemas["CustomerWorkspace"]>(`/accounts/${selected.value}`); }

async function load() {

  self.value = await portalRequest<Schemas["CustomerWorkspace"]>("/me");

  selected.value ||= self.value.customer.id;

  await loadAccount();

  const [family, status] = await Promise.all([portalRequest<Schemas["FamilyOut"][]>("/family"), portalRequest<{ available: boolean; sandbox: boolean }>("/payments/status")]);

  payment.value = status;

  const offers = await portalRequest<Schemas["Page_PackageOut_"]>("/topup-packages?limit=100");

  packages.value = offers.items;

  children.value = await Promise.all(family.map(async link => { const child = await portalRequest<Schemas["CustomerWorkspace"]>(`/accounts/${link.child_id}`); return { id: link.child_id, name: child.customer.full_name ?? "Child account" }; }));

}

async function signIn() { await run(async () => { const result = await portalRequest<Schemas["PortalToken"]>(invitation.value ? "/auth/enroll" : "/auth/login", { method: "POST", body: JSON.stringify(invitation.value ? { invitation_token: invitation.value, password: password.value } : { tenant_slug: tenant.value, email: email.value, password: password.value }) }); setPortalToken(result.access_token); invitation.value = ""; password.value = ""; await load(); }); }

async function signOut() { await run(async () => { try { await portalRequest("/auth/logout", { method: "POST" }); } finally { setPortalToken(null); self.value = null; account.value = null; children.value = []; checkout.value = null; } }); }

async function command(values: Record<string, string | number | null>, key: string) {

  await run(async () => {

    if (mode.value === "block") { if (values.confirmation !== "BLOCK") throw new Error("Type BLOCK to confirm"); await portalRequest(`/cards/${cardId.value}/block`, { method: "POST" }); }

    else if (mode.value === "topup") checkout.value = await portalRequest<Schemas["CheckoutOut"]>("/payments/checkouts", { method: "POST", body: JSON.stringify({ ...values, ...(chosenPackage.value ? { package_id: chosenPackage.value.id } : {}), idempotency_key: key }) });

    else await portalRequest(`/family/${selected.value}/${mode.value === 'fund' ? 'fund' : 'spending-limit'}`, { method: mode.value === "fund" ? "POST" : "PUT", body: JSON.stringify({ ...values, ...(mode.value === "fund" ? { idempotency_key: key } : {}) }) });

    mode.value = null;

    await load();

  });

}

async function settleSandbox() { await run(async () => { if (!checkout.value) return; checkout.value = await portalRequest<Schemas["CheckoutOut"]>(`/payments/checkouts/${checkout.value.session_id}/simulate`, { method: "POST" }); await load(); }); }

onMounted(async () => {

  invitation.value = new URLSearchParams(window.location.hash.slice(1)).get("invite") ?? "";

  if (invitation.value) window.history.replaceState(null, "", window.location.pathname);

  if (!invitation.value && await refreshPortal()) await run(load);

  loading.value = false;

});

</script>

<template>

  <main class="min-h-screen bg-subtle text-ink">

    <header class="border-b border-line bg-sidebar text-white"><div class="mx-auto flex max-w-5xl items-center justify-between px-5 py-5"><a href="/portal" class="text-lg font-extrabold tracking-wide">CASPRA <span class="font-normal opacity-75">My account</span></a><UiButton v-if="self" variant="secondary" :disabled="busy" @click="signOut">Sign out</UiButton></div></header>

    <DataState v-if="loading" message="Opening your account" />

    <section v-else-if="!self" class="mx-auto mt-12 max-w-md rounded border border-line bg-white p-7">

      <h1 class="text-xl font-bold">{{ invitation ? 'Activate your customer account' : 'Customer sign in' }}</h1>

      <p class="mb-6 mt-2 text-sm text-muted">{{ invitation ? 'Choose a password of at least 12 characters.' : 'Use the account issued by your venue.' }}</p>

      <form class="grid gap-4" @submit.prevent="signIn">

        <FormField v-if="!invitation" label="Venue code"><input v-model="tenant" autocomplete="organization" required /></FormField>

        <FormField v-if="!invitation" label="Email"><input v-model="email" type="email" autocomplete="username" required /></FormField>

        <FormField label="Password"><input v-model="password" type="password" :minlength="invitation ? 12 : 1" :autocomplete="invitation ? 'new-password' : 'current-password'" required /></FormField>

        <p v-if="error" role="alert" class="text-sm text-danger">{{ error }}</p><UiButton type="submit" :disabled="busy">{{ invitation ? 'Activate account' : 'Sign in' }}</UiButton>

      </form><p class="mt-5 text-xs text-muted">Need an account or password recovery? Ask your venue staff for a one-time link.</p>

    </section>

    <div v-else-if="account" class="mx-auto grid max-w-5xl gap-5 px-4 py-7 sm:px-6">

      <div class="flex flex-wrap items-center justify-between gap-3"><h1 class="text-2xl font-bold">{{ account.customer.full_name ?? 'Your account' }}</h1><label v-if="children.length" class="flex items-center gap-2 text-sm">Account<select v-model="selected" class="rounded border border-line bg-white p-2" @change="run(loadAccount)"><option :value="self.customer.id">{{ self.customer.full_name ?? 'My account' }}</option><option v-for="child in children" :key="child.id" :value="child.id">{{ child.name }}</option></select></label></div>

      <p v-if="error" role="alert" class="rounded border border-danger p-3 text-sm text-danger">{{ error }}</p>

      <section class="grid gap-3 sm:grid-cols-2" aria-label="Account balances"><article v-for="wallet in account.wallets" :key="wallet.id" class="rounded border border-line bg-white p-5"><p class="text-xs uppercase text-muted">{{ wallet.type === 'credit' ? 'Paid credit' : wallet.type === 'bonus' ? 'Bonus credit' : wallet.type }} · {{ wallet.currency }}</p><strong class="mt-2 block text-2xl">{{ formatMoney(wallet.balance_minor, wallet.currency) }}</strong><p class="mt-2 text-xs text-muted">Available {{ formatMoney(wallet.balance_minor - (account.reserved_minor[wallet.id] ?? 0), wallet.currency) }}</p></article></section>

      <label v-if="selected === self.customer.id && payment.available" class="grid gap-2 text-sm">Top-up offer<select v-model="packageId" class="rounded border border-line bg-white p-3"><option value="">Custom amount</option><option v-for="offer in packages" :key="offer.id" :value="offer.id">{{ offer.name }} · {{ formatMoney(offer.paid_minor, offer.currency) }} paid + {{ formatMoney(offer.bonus_minor, offer.currency) }} bonus</option></select></label>

      <div class="flex flex-wrap gap-3"><UiButton v-if="selected === self.customer.id" :disabled="!payment.available" @click="mode = 'topup'">Top up account</UiButton><UiButton v-else @click="mode = 'fund'">Allocate paid credit</UiButton><UiButton v-if="selected !== self.customer.id" variant="secondary" @click="mode = 'limit'">Set daily allowance</UiButton></div>

      <p v-if="!payment.available" class="text-sm text-muted">Online top-ups are unavailable. Visit the venue cashier to add credit.</p>

      <p v-if="payment.sandbox" class="rounded border border-warning bg-warning-soft p-3 text-sm">Sandbox payments · no real payment is taken.</p>

      <div v-if="checkout" class="rounded border border-line bg-white p-4 text-sm"><p>Top-up {{ checkout.status }}</p><UiButton v-if="payment.sandbox && checkout.status === 'started'" class="mt-3" :disabled="busy" @click="settleSandbox">Complete sandbox top-up</UiButton></div>

      <section v-if="account.spending_limits?.length" class="rounded border border-line bg-white p-4"><h2 class="font-semibold">Daily allowances</h2><p v-for="limit in account.spending_limits ?? []" :key="limit.id" class="mt-2 text-sm">{{ formatMoney(limit.daily_minor, limit.currency) }} per venue day</p></section>

      <section class="rounded border border-line bg-white p-5"><h2 class="font-bold">Cards</h2><div v-for="card in account.cards" :key="card.id" class="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3 text-sm"><span>{{ card.uid }} · {{ card.status }}</span><UiButton v-if="card.status === 'active'" variant="secondary" @click="cardId = card.id; mode = 'block'">Report lost card</UiButton></div></section>

      <section class="overflow-hidden rounded border border-line bg-white"><h2 class="p-4 font-bold">Latest transactions</h2><TransactionTable :transactions="account.transactions" /></section>

      <section class="rounded border border-line bg-white p-5"><h2 class="font-bold">Receipts</h2><p v-if="!account.receipts.length" class="mt-3 text-sm text-muted">No receipts yet.</p><div v-for="receipt in account.receipts" :key="receipt.id" class="mt-3 border-t border-line pt-3 text-sm">{{ receipt.number }} · {{ formatMoney(receipt.paid_minor, receipt.currency) }} paid + {{ formatMoney(receipt.bonus_minor, receipt.currency) }} bonus · {{ formatTime(receipt.created_at) }}</div></section>

      <section class="rounded border border-line bg-white p-5"><h2 class="font-bold">Machine plays</h2><p v-if="!account.plays.length" class="mt-3 text-sm text-muted">No plays yet.</p><div v-for="play in account.plays" :key="play.id" class="mt-3 flex justify-between border-t border-line pt-3 text-sm"><span>{{ play.price_snapshot.machine_name }} · {{ play.status }}</span><span>{{ formatMoney(play.amount_minor, play.currency) }}</span></div></section>

      <ActionDrawer :open="Boolean(mode)" :title="mode === 'block' ? 'Report lost card' : mode === 'fund' ? 'Allocate credit to child' : mode === 'limit' ? 'Set daily allowance' : 'Top up account'" :fields="fields" :currency="currency" :pending="busy" :error="error" @close="mode = null" @submit="command" />

    </div>

  </main>

</template>
