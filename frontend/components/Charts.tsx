"use client";

import { useEffect, useRef } from "react";
import Chart from "chart.js/auto";

const GRID = "#161618";
const TICK = "#5a5a54";
const monoFont = { family: "JetBrains Mono", size: 8.5 };

export function IhsgChart({ data }: { data: number[] }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const ctx = ref.current?.getContext("2d");
    if (!ctx) return;
    const today = new Date("2026-05-22");
    const labels: string[] = [];
    for (let i = data.length - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      labels.push(`${d.getDate()}/${d.getMonth() + 1}`);
    }
    const g = ctx.createLinearGradient(0, 0, 0, 230);
    g.addColorStop(0, "rgba(255,210,74,0.28)");
    g.addColorStop(1, "rgba(255,210,74,0)");

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            data,
            borderColor: "#ffd24a",
            backgroundColor: g,
            borderWidth: 2,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: "#ffe699",
            pointHoverBorderColor: "#000",
            pointHoverBorderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 1000, easing: "easeOutQuart" },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0a0a0b",
            borderColor: "#ffd24a",
            borderWidth: 1,
            padding: 9,
            titleColor: "#6e6e68",
            titleFont: { family: "JetBrains Mono", size: 9 },
            bodyColor: "#ffd24a",
            bodyFont: { family: "JetBrains Mono", size: 11, weight: "bold" },
            displayColors: false,
            callbacks: { label: (c) => "IHSG " + c.parsed.y.toLocaleString() },
          },
        },
        scales: {
          x: { grid: { color: GRID }, ticks: { color: TICK, font: monoFont, maxTicksLimit: 8 }, border: { display: false } },
          y: { position: "right", grid: { color: GRID }, ticks: { color: TICK, font: monoFont, callback: (v) => Number(v).toLocaleString() }, border: { display: false } },
        },
      },
    });
    return () => chart.destroy();
  }, [data]);

  return <canvas ref={ref} />;
}

export function EquityChart({ equity, benchmark }: { equity: number[]; benchmark: number[] }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const ctx = ref.current?.getContext("2d");
    if (!ctx) return;
    const labels: string[] = [];
    for (let i = 0; i < equity.length; i++) {
      const d = new Date(2022, 5, 1);
      d.setMonth(d.getMonth() + i);
      labels.push(`${d.getMonth() + 1}/${d.getFullYear() - 2000}`);
    }
    const g = ctx.createLinearGradient(0, 0, 0, 160);
    g.addColorStop(0, "rgba(255,210,74,0.2)");
    g.addColorStop(1, "rgba(255,210,74,0)");

    const chart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "Sahamflow", data: equity, borderColor: "#ffd24a", backgroundColor: g, borderWidth: 2, fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 4 },
          { label: "IHSG", data: benchmark, borderColor: "#3ad1ff", borderWidth: 1.3, borderDash: [3, 3], fill: false, tension: 0.3, pointRadius: 0, pointHoverRadius: 4 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 1200, easing: "easeOutQuart" },
        plugins: {
          legend: { display: true, position: "top", align: "end", labels: { color: "#a8a8a2", font: { family: "JetBrains Mono", size: 9 }, usePointStyle: true, padding: 12, boxWidth: 6 } },
          tooltip: { backgroundColor: "#0a0a0b", borderColor: "#ffd24a", borderWidth: 1, padding: 9, titleColor: "#6e6e68", titleFont: { family: "JetBrains Mono", size: 9 }, bodyColor: "#fff", bodyFont: { family: "JetBrains Mono", size: 10, weight: "bold" } },
        },
        scales: {
          x: { grid: { color: GRID }, ticks: { color: TICK, font: monoFont, maxTicksLimit: 8 }, border: { display: false } },
          y: { position: "right", grid: { color: GRID }, ticks: { color: TICK, font: monoFont, callback: (v) => v + "%" }, border: { display: false } },
        },
      },
    });
    return () => chart.destroy();
  }, [equity, benchmark]);

  return <canvas ref={ref} />;
}
