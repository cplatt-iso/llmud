import React, { useEffect, useState } from 'react';
import useGameStore from '../state/gameStore';
import { apiService } from '../services/apiService';
import './CharacterSelectionScreen.css';

function CharacterSelectionScreen() {
    // Select state and actions individually from the store.
    const characterList = useGameStore((state) => state.characterList);
    const setCharacterList = useGameStore((state) => state.setCharacterList);
    const selectCharacter = useGameStore((state) => state.selectCharacter);
    const token = useGameStore((state) => state.token);
    
    const startCharacterCreation = useGameStore((state) => state.startCharacterCreation);

    // Local state for this component's loading and error handling.
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');

    // This effect hook handles fetching character data.
    // It depends on `token` and `setCharacterList`.
    useEffect(() => {
        // Guard clause: Do not attempt to fetch if the token is not yet available.
        // This prevents the race condition.
        console.log('[CharSelect] useEffect running. Current token is:', token);
        if (!token) {
            return;
        }

        const getCharacters = async () => {
            try {
                // Call the apiService, now passing the token as an argument.
                const characters = await apiService.fetchCharacters(token);
                setCharacterList(characters);
            } catch (err) {
                console.error("Error in getCharacters:", err);
                setError('Failed to fetch characters. Please try logging in again.');
            } finally {
                setIsLoading(false);
            }
        };

        getCharacters();
    }, [token, setCharacterList]); // Dependency array makes this run only when token or setCharacterList changes.

    // This handler is called when a user clicks on a character card.
    const handleCharacterSelect = async (character) => {
        setIsLoading(true);
        setError('');
        try {
            // 1. Tell the backend which character is being selected.
            // This call also returns the character's current room data.
            const initialRoomData = await apiService.selectCharacterOnBackend(character.id, token);

            // 2. Create an updated character object that includes the current_room_id.
            // We'll pass this to the store so the map knows where to center initially.
            const characterForSession = {
                ...character,
                current_room_id: initialRoomData.id
            };

            // 3. Update our global state with the selected character data.
            // This single action will set the character info, room ID, and change the sessionState to 'IN_GAME'.
            selectCharacter(characterForSession);

        } catch (err) {
            console.error("Error in handleCharacterSelect:", err);
            setError(`Failed to select ${character.name}. Please try again.`);
            setIsLoading(false);
        }
        // On success, the component unmounts, so we don't need to touch isLoading.
    };

    // --- Conditional Rendering Logic ---

    // While waiting for the token to be set from the login screen.
    if (!token) {
        return <div className="loading-screen">Authenticating...</div>;
    }

    // After the token is set, while we are fetching characters.
    if (isLoading) {
        return <div className="loading-screen">Loading Characters...</div>;
    }

    // If something went wrong during the fetch.
    if (error) {
        return <div className="error-screen">{error}</div>;
    }

    // The main success view.
    return (
        <div className="char-select-container">
            <h2>Select a Character</h2>
            <div className="char-list">
                {characterList.length > 0 ? (
                    characterList.map((char) => (
                        <div key={char.id} className="char-card" onClick={() => handleCharacterSelect(char)}>
                            <h3>{char.name}</h3>
                            <p>{char.class_name} - Level {char.level}</p>
                        </div>
                    ))
                ) : (
                    // This message is now more accurate when no characters are loaded
                    <div className="no-chars-message">
                        <p>No characters found on this account.</p>
                    </div>
                )}
            </div>
            {/* The button to trigger the creation flow, which now calls the correctly pulled action */}
            <div className="char-creation-prompt">
                <button onClick={startCharacterCreation} className="create-char-button">
                    Create New Character
                </button>
            </div>
        </div>
    );
}

export default CharacterSelectionScreen;