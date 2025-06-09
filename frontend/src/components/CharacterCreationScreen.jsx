import React, { useEffect, useState } from 'react';
import useGameStore from '../state/gameStore';
import { apiService } from '../services/apiService';
import './CharacterCreationScreen.css';

function CharacterCreationScreen() {
    // Select state and actions individually to prevent re-render loops.
    const token = useGameStore(state => state.token);
    const classTemplates = useGameStore(state => state.classTemplates);
    const setClassTemplates = useGameStore(state => state.setClassTemplates);
    const finishCharacterCreation = useGameStore(state => state.finishCharacterCreation);
    
    // Local state for this component.
    const [name, setName] = useState('');
    const [selectedClass, setSelectedClass] = useState('');
    const [error, setError] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isClassesLoading, setIsClassesLoading] = useState(true);

    useEffect(() => {
        const fetchClasses = async () => {
            // If we already have the classes in our global store, just use them.
            if (classTemplates.length > 0) {
                // This ensures that even if the component re-renders, the state is set correctly.
                setSelectedClass(classTemplates[0].name);
                setIsClassesLoading(false);
                return;
            }
            
            // If we don't have the classes, fetch them.
            try {
                const templates = await apiService.fetchClassTemplates(token);
                setClassTemplates(templates);
                if (templates.length > 0) {
                    // Set the default selected class once the data arrives.
                    setSelectedClass(templates[0].name);
                }
            } catch (err) {
                setError('Could not load character classes from server. The blacksmith is on strike.');
            } finally {
                // This ALWAYS runs, ensuring the UI becomes usable.
                setIsClassesLoading(false);
            }
        };
        
        // Only run the fetch logic if we have a token.
        if (token) {
            fetchClasses();
        }
    }, [token, classTemplates, setClassTemplates]); // Dependencies are safe and explicit.

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!name.trim()) {
            setError('Character name cannot be empty.');
            return;
        }
        if (!selectedClass) {
            setError('Please select a character class.');
            return;
        }

        setIsSubmitting(true);
        setError('');
        try {
            const characterData = { name, class_name: selectedClass };
            await apiService.createCharacter(characterData, token);
            
            // Important: Clear the old character list so it re-fetches on the selection screen.
            useGameStore.getState().setCharacterList([]);
            
            // This sets the sessionState back to 'CHAR_SELECT'.
            finishCharacterCreation();

        } catch (err) {
            setError(err.data?.detail || 'An error occurred during character creation.');
        } finally {
            setIsSubmitting(false);
        }
    };
    
    return (
        <div className="char-create-container">
            <form className="char-create-form" onSubmit={handleSubmit}>
                <h2>Create a New Hero</h2>
                {error && <p className="error-message">{error}</p>}
                
                <div className="form-group">
                    <label htmlFor="char-name">Character Name</label>
                    <input
                        id="char-name"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                        maxLength="50"
                        pattern="^[a-zA-Z0-9_]+$"
                        title="Name can only contain letters, numbers, and underscores."
                        disabled={isSubmitting}
                    />
                </div>

                <div className="form-group">
                    <label htmlFor="char-class">Class</label>
                    <select
                        id="char-class"
                        value={selectedClass}
                        onChange={(e) => setSelectedClass(e.target.value)}
                        disabled={isClassesLoading || isSubmitting}
                    >
                        {isClassesLoading ? (
                            <option>Loading classes...</option>
                        ) : (
                            classTemplates.map(template => (
                                // This is your correct fix for the option value.
                                <option key={template.id} value={template.name}>
                                    {template.name}
                                </option>
                            ))
                        )}
                    </select>
                </div>
                
                <button 
                    type="submit" 
                    disabled={isSubmitting || isClassesLoading}
                >
                    {isSubmitting ? 'Creating...' : 'Forge Your Destiny'}
                </button>
            </form>
        </div>
    );
}

export default CharacterCreationScreen;