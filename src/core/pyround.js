/**
 * pyRound - pembulatan "banker's rounding" (round half to even)
 * untuk memastikan hasil identik dengan Python built-in round().
 * Dipakai untuk konsistensi 1 rupiah dengan backend Python.
 */
export function pyRound(num, decimals = 0) {
    const factor = Math.pow(10, decimals);
    const n = num * factor;
    const floor = Math.floor(n);
    const diff = n - floor;

    if (Math.abs(diff - 0.5) < 1e-9) {
        // Exactly .5 - round to nearest even
        return (floor % 2 === 0 ? floor : floor + 1) / factor;
    }
    return Math.round(n) / factor;
}
