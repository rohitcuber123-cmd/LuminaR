export const comparison = String.raw`### Differences Between Pure ALOHA and Slotted ALOHA

#### Vulnerable Time

- **Pure ALOHA:** The vulnerable time is \(2 \times T_{\text{fr}}\) seconds.
- **Slotted ALOHA:** The vulnerable time is \(T_{\text{fr}}\) seconds.

| Feature | Pure ALOHA | Slotted ALOHA |
| --- | --- | --- |
| Transmission | Anytime | Slot boundaries |
| Vulnerable time | \(2 \times T_{\text{fr}}\) | \(T_{\text{fr}}\) |

*Technical literal:* <tick>10101011<tick>; 2 seconds; 0.184; 36.8%.

1. Read the frame.
2. Check its timing.

> Compare against the source.

\[T_{\frac{\text{slot}}{2}} = \frac{2T}{3}\]

<tick><tick><tick>text
10101011 and literal \(2 \times T\) stay unchanged.
<tick><tick><tick>
`.replaceAll('<tick>', '`')

export const wideTable = '| ' + Array.from({ length: 12 }, (_, i) => 'Column ' + i).join(' | ') + ' |\n| ' + Array(12).fill('---').join(' | ') + ' |\n| ' + Array(12).fill('Preserved cell 10101011').join(' | ') + ' |'
export const longMath = '$$\n' + Array(45).fill('T_{\\text{fr}}').join(' + ') + ' = 10101011\n$$'
export const wideCode = '\n```text\n' + '10101011'.repeat(100) + '\n```\n'
