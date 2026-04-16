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
      <h1 className="font-figtree">Hello World Figtree</h1>
      <h1 className="font-manrope">Hello World Figtree</h1>
    </div>
  );
}
