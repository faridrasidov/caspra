<script setup lang="ts">
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { computed } from "vue";
import { Line } from "vue-chartjs";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

const props = defineProps<{
  rows: { day: string; load: number; spend: number }[];
  currency: string;
}>();

const chartData = computed<ChartData<"line">>(() => ({
  labels: props.rows.map((row) => row.day),
  datasets: [
    {
      label: "Load",
      data: props.rows.map((row) => row.load),
      borderColor: "#2457d6",
      backgroundColor: "#2457d6",
      borderWidth: 2,
      pointRadius: props.rows.length === 1 ? 3 : 0,
      pointHoverRadius: 4,
      tension: 0.32,
    },
    {
      label: "Spend",
      data: props.rows.map((row) => row.spend),
      borderColor: "#16833b",
      backgroundColor: "#16833b",
      borderWidth: 2,
      pointRadius: props.rows.length === 1 ? 3 : 0,
      pointHoverRadius: 4,
      tension: 0.32,
    },
  ],
}));

const chartStep = computed(() => {
  const maximum = Math.max(
    0,
    ...props.rows.flatMap((row) => [row.load, row.spend]),
  );
  if (maximum === 0) return 1;
  const rawStep = maximum / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  const factor = normalized <= 1
    ? 1
    : normalized <= 1.5
      ? 1.5
      : normalized <= 2
        ? 2
        : normalized <= 2.5
          ? 2.5
          : normalized <= 5
            ? 5
            : 10;
  return factor * magnitude;
});

const options = computed<ChartOptions<"line">>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { intersect: false, mode: "index" },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label(context) {
          return `${context.dataset.label}: ${new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: props.currency,
          }).format(Number(context.parsed.y))}`;
        },
      },
    },
  },
  scales: {
    x: {
      offset: true,
      border: { display: false },
      grid: { color: "#e6e8eb", drawTicks: false, borderDash: [3, 3] },
      ticks: { color: "#626a73", padding: 8, font: { size: 10 } },
    },
    y: {
      beginAtZero: true,
      max: chartStep.value * 4,
      border: { display: false },
      grid: { color: "#e6e8eb", drawTicks: false, borderDash: [3, 3] },
      ticks: {
        color: "#626a73",
        padding: 8,
        stepSize: chartStep.value,
        font: { size: 10 },
      },
    },
  },
}));
</script>

<template>
  <Line :data="chartData" :options="options" />
</template>
