import json

with open('zia_work_dump.json', 'r') as f:
    data = json.load(f)

# print(data)

for zia_row in data:
    for (zia_choice_i, zia_choice) in enumerate(zia_row):
        # print(zia_choice)
        if zia_choice_i == 0:
            print('[', end='')
        else:
            print(' ', end='')

        if zia_choice == 'inpin':
            print('XC2ZIAInput::DedicatedInput', end='')
        elif zia_choice[2] == 'mc':
            print('XC2ZIAInput::Macrocell{{fb: {}, mc: {}}}'.format(zia_choice[0], zia_choice[1]), end='')
        else:
            print('XC2ZIAInput::IBuf{{ibuf: {}}}'.format(zia_choice[0] * 16 + zia_choice[1]), end='')

        if zia_choice_i == len(zia_row) - 1:
            print('],\n')
        else:
            print(',')