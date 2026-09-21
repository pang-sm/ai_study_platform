import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PasswordField } from './password-field';

function Reveal() {
  return (
    <PasswordField
      label="密码"
      name="password"
      autoComplete="current-password"
      defaultValue="hunter2"
    />
  );
}

describe('password field', () => {
  it('shows and hides the typed password without replacing the input', async () => {
    render(<Reveal />);
    const input = screen.getByLabelText('密码');
    expect(input).toHaveAttribute('type', 'password');

    await userEvent.click(screen.getByRole('button', { name: '显示密码' }));
    // The same node, so the value and the caret survive the toggle.
    expect(screen.getByLabelText('密码')).toBe(input);
    expect(input).toHaveAttribute('type', 'text');

    await userEvent.click(screen.getByRole('button', { name: '隐藏密码' }));
    expect(input).toHaveAttribute('type', 'password');
    expect(input).toHaveValue('hunter2');
  });

  it('names the toggle and states which state it is in', async () => {
    render(<Reveal />);
    const toggle = screen.getByRole('button', { name: '显示密码' });
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    expect(toggle).toHaveAttribute('aria-controls', screen.getByLabelText('密码').id);

    await userEvent.click(toggle);
    expect(screen.getByRole('button', { name: '隐藏密码' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('is operable from the keyboard and puts the caret back in the field', async () => {
    render(<PasswordField label="密码" name="password" autoComplete="current-password" />);
    const input = screen.getByLabelText('密码');

    // Typing leaves the caret at the end, which is the state the reveal control has to preserve.
    await userEvent.type(input, 'hunter2');
    expect(input).toHaveValue('hunter2');

    // One Tab reaches the toggle — it is after the field in the tab sequence, not before it —
    // and Enter activates it.
    await userEvent.tab();
    expect(screen.getByRole('button', { name: '显示密码' })).toHaveFocus();
    await userEvent.keyboard('{Enter}');

    expect(input).toHaveAttribute('type', 'text');
    // Focus comes back to the field, so the next keystroke continues the password instead of
    // activating the button a second time.
    expect(input).toHaveFocus();
    await userEvent.keyboard('!');
    expect(input).toHaveValue('hunter2!');
  });

  it('leaves the input’s own attributes alone so autofill still applies', () => {
    render(<Reveal />);
    const input = screen.getByLabelText('密码');
    expect(input).toHaveAttribute('autocomplete', 'current-password');
    expect(input).toHaveAttribute('name', 'password');
  });

  it('keeps the caller’s ref, which is how the form reads the value', async () => {
    // `ref` is what react-hook-form registers a field with. If the reveal control took it over,
    // the field would submit as `undefined` — the failure this asserts against.
    const ref = { current: null as HTMLInputElement | null };
    render(<PasswordField label="密码" name="password" ref={ref} />);

    await userEvent.type(screen.getByLabelText('密码'), 'abc');
    expect(ref.current).toBe(screen.getByLabelText('密码'));
    expect(ref.current).toHaveValue('abc');
  });

  it('wires its error text to the field rather than leaving it as loose prose', () => {
    render(<PasswordField label="确认密码" name="confirm" error="两次输入的密码不一致" />);
    const input = screen.getByLabelText('确认密码');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    const describedBy = input.getAttribute('aria-describedby');
    expect(describedBy).toBeTruthy();
    expect(document.getElementById(describedBy ?? '')).toHaveTextContent('两次输入的密码不一致');
  });

  it('does not turn the label itself into the toggle', () => {
    // A control nested in a label is activated by the label click that is meant to focus the
    // field, so the two must not be related by containment.
    render(<Reveal />);
    const label = screen.getByText('密码', { selector: 'label' });
    expect(label.querySelector('button')).toBeNull();
  });
});

describe('password field value stays the caller’s', () => {
  it('reports what was typed to a controlled caller', async () => {
    const onChange = vi.fn();
    render(<PasswordField label="密码" name="password" onChange={onChange} />);
    await userEvent.type(screen.getByLabelText('密码'), 'a');
    expect(onChange).toHaveBeenCalled();
  });
});
