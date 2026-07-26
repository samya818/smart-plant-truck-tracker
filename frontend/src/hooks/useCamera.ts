import { useState, useRef, useCallback } from 'react';

export function useCamera() {
  const [photo, setPhoto] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const triggerCapture = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleCapture = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    setFile(selected);
    const reader = new FileReader();
    reader.onloadend = () => setPhoto(reader.result as string);
    reader.readAsDataURL(selected);
  }, []);

  const clearPhoto = useCallback(() => {
    setPhoto(null);
    setFile(null);
    if (inputRef.current) inputRef.current.value = '';
  }, []);

  return { photo, file, inputRef, triggerCapture, handleCapture, clearPhoto };
}
