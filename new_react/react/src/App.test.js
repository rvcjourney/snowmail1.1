import { render, screen } from '@testing-library/react';
import App from './App';

test('renders Email Extractor heading', () => {
  render(<App />);
  const heading = screen.getByText(/Email Extractor/i);
  expect(heading).toBeInTheDocument();
});

test('renders Start Extraction button', () => {
  render(<App />);
  const button = screen.getByText(/Start Extraction/i);
  expect(button).toBeInTheDocument();
});
