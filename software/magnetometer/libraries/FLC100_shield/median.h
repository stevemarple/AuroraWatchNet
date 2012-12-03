/*
 * Algorithm from N. Wirth's book, implementation by N. Devillard.
 * This code in public domain.
 *
 * Adapted to templated C++ version by Steve Marple.
 */


template <typename T>
T kth_smallest(T a[], int n, int k);

template <typename T>
inline T median(T a[], int n)
{
  return kth_smallest(a, n, (((n)&1)?((n)/2):(((n)/2)-1)));
}
