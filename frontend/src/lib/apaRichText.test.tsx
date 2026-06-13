import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { ApaRichText } from '../components/analysis/ApaRichText';

describe('ApaRichText', () => {
  it('renders plain text escaped', () => {
    const { container } = render(<ApaRichText value={'a < b & c'} />);
    expect(container.textContent).toBe('a < b & c');
    expect(container.querySelector('script')).toBeNull();
  });

  it('renders em tags as italic', () => {
    const { container } = render(<ApaRichText value={'p değeri <em>p</em> idi'} />);
    expect(container.querySelector('em')?.textContent).toBe('p');
  });

  it('strips unknown html tags', () => {
    const { container } = render(<ApaRichText value={'<img alt="x">metin'} />);
    expect(container.textContent).toBe('metin');
  });
});
