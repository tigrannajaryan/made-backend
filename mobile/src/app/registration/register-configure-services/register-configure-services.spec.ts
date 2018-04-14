import { ComponentFixture, async } from '@angular/core/testing';
import { TestUtils } from '../../../test';
import { RegisterConfigureServicesPage } from './register-configure-services';

let fixture: ComponentFixture<RegisterConfigureServicesPage> = null;
let instance: any = null;

describe('Pages: RegisterConfigureServicesPage', () => {

    beforeEach(async(() => TestUtils.beforeEachCompiler([RegisterConfigureServicesPage]).then(compiled => {
        fixture = compiled.fixture;
        instance = compiled.instance;
    })));

    it('should create the RegisterConfigureServicesPage', async(() => {
        expect(instance).toBeTruthy();
    }));

    it('should have 2 services', async(() => {
        expect(instance.services).toEqual(
            [
                { name: 'Haircut', price: 70 },
                { name: 'Nails', price: 30 }
            ]
        );
    }));

    it('should have navCtrl and navParams', async(() => {
        expect(instance.navCtrl).toBeTruthy();
        expect(instance.navParams).toBeTruthy();
    }));

});