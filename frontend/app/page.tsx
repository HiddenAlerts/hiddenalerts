import { useState } from 'react';

export default function Home() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!email) return;
    console.log('Captured email:', email); // temporary
    setSubmitted(true);
  };

  return (
    <div className="flex flex-col">
      <h1>Hello World</h1>
    </div>
  );
}
