/**
 * Konstanta yang dipakai bersama oleh calculator.js dan modul handling
 * per-carrier (handling_ups.js, handling_fedex.js). Dipisah ke file sendiri
 * supaya tidak ada circular import (handling_fedex.js butuh PPN_RATE, tapi
 * calculator.js juga butuh import dari handling_fedex.js).
 */

export const PPN_RATE = 0.11 // 11% -- tarif PPN Indonesia
