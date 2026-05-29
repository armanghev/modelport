export function buildUsageBars(seed: number): number[] {
  const bars: number[] = [];
  let state = (seed % 97) + 11;

  for (let index = 0; index < 20; index += 1) {
    state = (state * 17 + 31 + index * 7) % 89;
    bars.push((state % 9) + 1);
  }

  return bars;
}

export function buildDailyUsageValues(
  usageBars: number[],
  tokenTotal: number,
): number[] {
  const values = usageBars.slice(-7);
  const sum = values.reduce((acc, value) => acc + value, 0);

  if (sum === 0) {
    return values.map(() => 0);
  }

  return values.map((value) => Math.round((tokenTotal * value) / sum));
}

export function buildHourlyUsageValues(dailyValues: number[], seed: number): number[] {
  const hourlyValues: number[] = [];
  let state = (seed % 997) + 97;

  dailyValues.forEach((dailyTotal, dayIndex) => {
    const weights: number[] = [];
    let weightSum = 0;

    for (let hour = 0; hour < 24; hour += 1) {
      state = (state * 37 + 19 + dayIndex * 13 + hour * 11) % 1009;
      const noise = (state % 100) / 100;
      const diurnal = 0.55 + 0.45 * Math.sin(((hour - 6) / 24) * Math.PI * 2);
      const weight = Math.max(0.12, diurnal + noise * 0.28);
      weights.push(weight);
      weightSum += weight;
    }

    const dayHourly = weights.map((weight) =>
      Math.max(0, Math.round((dailyTotal * weight) / weightSum)),
    );

    const allocated = dayHourly.reduce((sum, value) => sum + value, 0);
    const remainder = dailyTotal - allocated;
    if (remainder !== 0) {
      const peakIndex = dayHourly.indexOf(Math.max(...dayHourly));
      dayHourly[peakIndex] = Math.max(0, dayHourly[peakIndex] + remainder);
    }

    hourlyValues.push(...dayHourly);
  });

  return hourlyValues;
}

export function downsampleSeries(values: number[], sampleCount: number): number[] {
  if (values.length <= sampleCount) {
    return values;
  }

  const sampled: number[] = [];
  for (let index = 0; index < sampleCount; index += 1) {
    const sourceIndex = Math.round((index * (values.length - 1)) / (sampleCount - 1));
    sampled.push(values[sourceIndex]);
  }

  return sampled;
}

